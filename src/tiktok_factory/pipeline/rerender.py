"""Re-render already materialized clips without invoking a video generator."""

import json
import re
import wave
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Any, Protocol

from tiktok_factory.pipeline.renderer import FFmpegRenderer, probe
from tiktok_factory.pipeline.typography import TextOverlay, render_text_card
from tiktok_factory.providers.base import TextToSpeechProvider
from tiktok_factory.qa.reviews import review_audio_probe, review_text_layout, review_technical
from uuid import uuid4


AUDIO_TRAILING_SILENCE_SECONDS = 0.35
MAX_NARRATION_TEMPO = 1.25


class ExistingMediaRenderer(Protocol):
    def render(
        self, clips: list[Path], destination: Path, hook: str = "",
        audio_path: Path | None = None, normalize_audio: bool = True,
        overlays: list[TextOverlay] | None = None, audio_tempo: float = 1.0,
        target_duration: float | None = None,
    ) -> Path: ...


@dataclass(frozen=True)
class RerenderResult:
    video: Path
    audio: Path
    clips: tuple[Path, ...]
    metadata: Path
    qa: dict[str, Any]


def _natural_key(path: Path) -> list[int | str]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(path))]


def wav_duration(path: Path) -> float:
    """Return PCM WAV duration without invoking a second media process."""
    try:
        with wave.open(str(path), "rb") as reader:
            frame_rate = reader.getframerate()
            if frame_rate <= 0:
                raise RuntimeError("TTS WAV has an invalid sample rate")
            return reader.getnframes() / frame_rate
    except (OSError, EOFError, wave.Error) as exc:
        raise RuntimeError("TTS provider returned an unreadable WAV file") from exc


def plan_narration_tempo(
    audio_duration: float,
    video_duration: float,
    trailing_silence: float = AUDIO_TRAILING_SILENCE_SECONDS,
    max_tempo: float = MAX_NARRATION_TEMPO,
) -> float:
    """Fit the complete narration before the end card without truncating speech."""
    if audio_duration <= 0 or video_duration <= 0:
        raise ValueError("audio and video durations must be positive")
    if trailing_silence < 0 or trailing_silence >= video_duration:
        raise ValueError("trailing silence must fit inside the video")
    budget = video_duration - trailing_silence
    tempo = max(1.0, audio_duration / budget)
    if tempo > max_tempo:
        raise ValueError(
            "narration is too long for the existing video assets: "
            f"audio={audio_duration:.3f}s video={video_duration:.3f}s "
            f"required_tempo={tempo:.3f} max_tempo={max_tempo:.3f}"
        )
    return tempo


def load_metadata(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read metadata JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("metadata root must be an object")
    return value


def discover_clips(input_dir: Path, metadata: dict[str, Any]) -> list[Path]:
    if not input_dir.is_dir():
        raise ValueError(f"input directory does not exist: {input_dir}")
    clips = sorted((p for p in input_dir.rglob("*.mp4") if p.is_file()), key=_natural_key)
    # Prefer the filenames recorded as metadata, but only as hints: those paths were
    # runner-local storage keys and are never treated as downloadable Supabase objects.
    hints = [Path(str(a.get("path", a.get("storage_key", "")))).name
             for a in metadata.get("assets", []) if isinstance(a, dict)]
    by_name = {clip.name: clip for clip in clips}
    hinted = [by_name[name] for name in hints if name in by_name]
    if hinted and len(hinted) == len(hints):
        clips = hinted
    if not clips:
        raise ValueError(f"no MP4 clips found under {input_dir}")
    if len({p.resolve() for p in clips}) != len(clips):
        raise ValueError("metadata resolves to duplicate clips")
    return clips


class ExistingClipsRerenderer:
    def __init__(
        self,
        tts: TextToSpeechProvider,
        renderer: ExistingMediaRenderer | None = None,
        probe_fn: Callable[[Path], dict[str, Any]] = probe,
        audio_duration_fn: Callable[[Path], float] = wav_duration,
    ):
        self.tts = tts
        self.renderer = renderer or FFmpegRenderer()
        self.probe_fn = probe_fn
        self.audio_duration_fn = audio_duration_fn

    def run(self, input_dir: Path, metadata_path: Path, output_dir: Path) -> RerenderResult:
        metadata = load_metadata(metadata_path)
        clips = discover_clips(input_dir, metadata)
        script = metadata.get("script", {})
        if not isinstance(script, dict):
            raise ValueError("metadata.script must be an object")
        hook = str(script.get("hook", "")).strip()
        cta = str(script.get("call_to_action", "")).strip()
        narration = " ".join(
            str(script.get(field, "")).strip()
            for field in ("hook", "narration", "call_to_action")
            if str(script.get(field, "")).strip()
        )
        if not narration:
            raise ValueError("metadata must contain script narration")
        output_dir.mkdir(parents=True, exist_ok=True)
        durations = [float(self.probe_fn(clip)["format"]["duration"]) for clip in clips]
        duration = sum(durations)
        overlays: list[TextOverlay] = []
        if hook:
            overlays.append(render_text_card(hook, output_dir / "overlays" / "hook.png",
                                             start_time=0.2, end_time=min(3.0, duration), y=180))
        if cta and duration > 1:
            cta_end = max(0.1, duration - 0.2)
            overlays.append(render_text_card(
                cta, output_dir / "overlays" / "cta.png",
                start_time=max(0.2, cta_end - 2.5), end_time=cta_end, y=1500, max_lines=2,
                initial_size=64, minimum_size=34,
            ))
        (output_dir / "audio").mkdir(parents=True, exist_ok=True)
        audio = self.tts.synthesize(narration, output_dir / "audio" / "narration.wav")
        source_audio_duration = self.audio_duration_fn(audio)
        audio_tempo = plan_narration_tempo(source_audio_duration, duration)
        final = self.renderer.render(
            clips, output_dir / "final.mp4", "", audio, True, overlays,
            audio_tempo=audio_tempo, target_duration=duration,
        )
        qa = self.probe_fn(final)
        video_id = uuid4()
        idea_id_raw = metadata.get("idea", {}).get("id") if isinstance(metadata.get("idea"), dict) else metadata.get("source_idea_id")
        idea_id = str(idea_id_raw or "")
        text_review = review_text_layout(video_id, overlays, duration)
        audio_review = review_audio_probe(video_id, qa, require_audio=True)
        technical_review = review_technical(video_id, final, require_audio=True, probe_data=qa)
        manifest = output_dir / "metadata.json"
        manifest.write_text(json.dumps({
            "source_idea_id": idea_id,
            "rerender_mode": "existing_assets",
            "runway_calls": 0,
            "hook_render_strategy": "pillow_overlay",
            "audio_provider": "groq_tts",
            "source_audio_duration_seconds": round(source_audio_duration, 6),
            "audio_tempo": round(audio_tempo, 6),
            "audio_target_duration_seconds": round(duration, 6),
            "audio_trailing_silence_seconds": AUDIO_TRAILING_SILENCE_SECONDS,
            "source_metadata": str(metadata_path),
            "physical_clips": [str(path.resolve()) for path in clips],
            "video": str(final),
            "audio": str(audio),
            "overlays": [item.metadata() for item in overlays],
            "qa_text": text_review.model_dump(mode="json"),
            "qa_audio": audio_review.model_dump(mode="json"),
            "qa_technical": technical_review.model_dump(mode="json"),
            "ffprobe": qa,
        }, indent=2), encoding="utf-8")
        return RerenderResult(final, audio, tuple(clips), manifest, qa)
