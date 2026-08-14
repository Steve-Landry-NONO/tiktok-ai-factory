from pathlib import Path
from uuid import UUID

from tiktok_factory.domain.models import CreativeScores, QAOutcome, QAReview
from tiktok_factory.pipeline.renderer import probe


def creative_outcome(score: float) -> QAOutcome:
    if score >= 85: return QAOutcome.PASS
    if score >= 75: return QAOutcome.RETRYABLE
    return QAOutcome.FAIL


def review_creative(video_id: UUID, scores: CreativeScores) -> QAReview:
    return QAReview(video_id=video_id, kind="creative", outcome=creative_outcome(scores.overall_score),
                    score=scores.overall_score, checks={"artifact_risk": scores.artifact_risk <= 30})


def review_technical(video_id: UUID, path: Path, max_size_mb: float = 100, require_audio: bool = False) -> QAReview:
    checks = {"exists": path.is_file(), "non_empty": path.is_file() and path.stat().st_size > 0}
    diagnostics: list[str] = []
    if not all(checks.values()):
        return QAReview(video_id=video_id, kind="technical", outcome=QAOutcome.FAIL, checks=checks,
                        diagnostics=["file missing or empty"])
    try: data = probe(path)
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
       "max_size": path.stat().st_size <= max_size_mb * 1024 * 1024})
    diagnostics.extend(k for k, ok in checks.items() if not ok)
    return QAReview(video_id=video_id, kind="technical", outcome=QAOutcome.PASS if all(checks.values()) else QAOutcome.FAIL,
                    checks=checks, diagnostics=diagnostics)
