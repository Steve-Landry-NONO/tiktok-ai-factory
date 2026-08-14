from pathlib import Path
from typing import Any, cast
from uuid import UUID

from tiktok_factory.domain.models import CreativeScores, QAOutcome, QAReview
from tiktok_factory.pipeline.renderer import probe
from tiktok_factory.pipeline.typography import TextOverlay


def creative_outcome(score: float) -> QAOutcome:
    if score >= 85: return QAOutcome.PASS
    if score >= 75: return QAOutcome.RETRYABLE
    return QAOutcome.FAIL


def review_creative(video_id: UUID, scores: CreativeScores) -> QAReview:
    return QAReview(video_id=video_id, kind="creative", outcome=creative_outcome(scores.overall_score),
                    score=scores.overall_score, checks={"artifact_risk": scores.artifact_risk <= 30})


def review_technical(
    video_id: UUID, path: Path, max_size_mb: float = 100, require_audio: bool = False,
    probe_data: dict[str, object] | None = None,
) -> QAReview:
    checks = {"exists": path.is_file(), "non_empty": path.is_file() and path.stat().st_size > 0}
    diagnostics: list[str] = []
    if not all(checks.values()):
        return QAReview(video_id=video_id, kind="technical", outcome=QAOutcome.FAIL, checks=checks,
                        diagnostics=["file missing or empty"])
    try: data = cast(dict[str, Any], probe_data) if probe_data is not None else probe(path)
    except RuntimeError as exc:
        return QAReview(video_id=video_id, kind="technical", outcome=QAOutcome.FAIL, checks={**checks, "probe": False}, diagnostics=[str(exc)])
    streams = data.get("streams", []); videos = [s for s in streams if s.get("codec_type") == "video"]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    video = videos[0] if videos else {}
    try:
        num, den = video.get("avg_frame_rate", "0/1").split("/"); fps = float(num) / float(den)
        duration = float(data.get("format", {}).get("duration", 0))
    except (ValueError, ZeroDivisionError): fps = duration = 0
    checks.update({"probe": True, "video_stream": bool(videos), "codec_h264": video.get("codec_name") == "h264",
       "resolution": (video.get("width"), video.get("height")) == (1080, 1920), "aspect_ratio": video.get("display_aspect_ratio") in ("9:16", ""),
       "duration": duration > 0, "fps": abs(fps - 30) < .1, "audio": bool(audios) if require_audio else True,
       "audio_aac": (bool(audios) and audios[0].get("codec_name") == "aac") if require_audio else True,
       "max_size": path.stat().st_size <= max_size_mb * 1024 * 1024})
    diagnostics.extend(k for k, ok in checks.items() if not ok)
    return QAReview(video_id=video_id, kind="technical", outcome=QAOutcome.PASS if all(checks.values()) else QAOutcome.FAIL,
                    checks=checks, diagnostics=diagnostics)


def review_text_layout(
    video_id: UUID, overlays: list[TextOverlay], duration: float,
    width: int = 1080, height: int = 1920,
) -> QAReview:
    safe_x = round(width * 0.1)
    checks: dict[str, bool] = {"has_hook": bool(overlays)}
    for index, item in enumerate(overlays):
        prefix = "hook" if index == 0 else f"overlay_{index}"
        minimum_font = 42 if index == 0 else 34
        checks.update({
            f"{prefix}_in_frame": item.box_x >= 0 and item.box_y >= 0
            and item.box_x + item.box_width <= width and item.box_y + item.box_height <= height,
            f"{prefix}_safe_zone": item.safe_zone_ok and item.box_x >= safe_x
            and item.box_x + item.box_width <= width - safe_x,
            f"{prefix}_lines": 0 < item.line_count <= item.max_lines,
            f"{prefix}_font": item.font_size >= minimum_font,
            f"{prefix}_interval": 0 <= item.start_time < item.end_time <= duration,
        })
    if overlays:
        checks["hook_not_full_duration"] = overlays[0].start_time >= 0.2 and overlays[0].end_time <= 3.0
        checks["hook_vertical_zone"] = 180 <= overlays[0].box_y <= 420
    diagnostics = [name for name, passed in checks.items() if not passed]
    return QAReview(video_id=video_id, kind="text", outcome=QAOutcome.PASS if all(checks.values()) else QAOutcome.FAIL,
                    checks=checks, diagnostics=diagnostics)


def review_audio_probe(video_id: UUID, data: dict[str, object], require_audio: bool = True) -> QAReview:
    streams = data.get("streams", [])
    streams = streams if isinstance(streams, list) else []
    audio = next((item for item in streams if isinstance(item, dict) and item.get("codec_type") == "audio"), None)
    video = next((item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"), None)
    fmt = data.get("format", {})
    fmt = fmt if isinstance(fmt, dict) else {}
    try:
        format_duration = float(fmt.get("duration", 0))
        audio_duration = float(audio.get("duration", format_duration)) if audio else 0
        video_duration = float(video.get("duration", format_duration)) if video else 0
    except (TypeError, ValueError):
        format_duration = audio_duration = video_duration = 0
    duration_tolerance = max(1.0, video_duration * 0.05) if video_duration > 0 else 0
    duration_delta = abs(audio_duration - video_duration)
    checks = {
        "audio_stream": bool(audio) if require_audio else True,
        "audio_codec": bool(audio and audio.get("codec_name")),
        "audio_non_empty": audio_duration > 0,
        "duration_coherent": (
            format_duration > 0
            and video_duration > 0
            and audio_duration > 0
            and duration_delta <= duration_tolerance
        ),
    }
    diagnostics = [name for name, passed in checks.items() if not passed]
    if not checks["duration_coherent"]:
        diagnostics.append(
            "durations "
            f"audio={audio_duration:.3f}s video={video_duration:.3f}s "
            f"format={format_duration:.3f}s delta={duration_delta:.3f}s "
            f"tolerance={duration_tolerance:.3f}s"
        )
    return QAReview(video_id=video_id, kind="audio", outcome=QAOutcome.PASS if all(checks.values()) else QAOutcome.FAIL,
                    checks=checks, diagnostics=diagnostics)
