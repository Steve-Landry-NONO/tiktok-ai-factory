import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from tiktok_factory.providers.local import require_tool
from tiktok_factory.pipeline.typography import TextOverlay


@dataclass(frozen=True)
class VideoProfile:
    name: str = "tiktok_vertical_v1"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    video_codec: str = "libx264"
    audio_codec: str = "aac"

PROFILE = VideoProfile()


def probe(path: Path, ffprobe: str = "ffprobe") -> dict[str, Any]:
    require_tool(ffprobe)
    cmd = [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode: raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")
    return cast(dict[str, Any], json.loads(result.stdout))


class FFmpegRenderer:
    def __init__(self, ffmpeg: str = "ffmpeg", profile: VideoProfile = PROFILE):
        self.ffmpeg, self.profile = ffmpeg, profile

    def command(
        self,
        clips: list[Path],
        destination: Path,
        hook: str = "",
        audio_path: Path | None = None,
        normalize_audio: bool = True,
        overlays: list[TextOverlay] | None = None,
        audio_tempo: float = 1.0,
        target_duration: float | None = None,
    ) -> list[str]:
        if not clips: raise ValueError("at least one clip is required")
        if audio_tempo <= 0: raise ValueError("audio_tempo must be positive")
        if target_duration is not None and target_duration <= 0:
            raise ValueError("target_duration must be positive")
        inputs = [item for clip in clips for item in ("-i", str(clip))]
        if audio_path is not None:
            inputs.extend(("-i", str(audio_path)))
        overlays = overlays or []
        for overlay in overlays:
            inputs.extend(("-i", str(overlay.path)))
        filters = []
        for i in range(len(clips)):
            filters.append(f"[{i}:v]scale={self.profile.width}:{self.profile.height}:force_original_aspect_ratio=decrease,"
                           f"pad={self.profile.width}:{self.profile.height}:(ow-iw)/2:(oh-ih)/2,fps={self.profile.fps},"
                           f"setsar=1,format=yuv420p[v{i}]")
        filters.append("".join(f"[v{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=0[vcat]")
        output = "[vcat]"
        if hook and not overlays:
            safe = hook.replace("'", "’").replace(":", "\\:")
            filters.append(f"[vcat]drawtext=text='{safe}':fontcolor=white:fontsize=64:x=(w-text_w)/2:y=180:"
                           "box=1:boxcolor=black@0.6:boxborderw=20[vout]")
            output = "[vout]"
        for index, overlay in enumerate(overlays):
            overlay_input = len(clips) + (1 if audio_path is not None else 0) + index
            next_output = f"[overlay{index}]"
            filters.append(
                f"{output}[{overlay_input}:v]overlay={overlay.box_x}:{overlay.box_y}:"
                f"enable='between(t,{overlay.start_time},{overlay.end_time})'{next_output}"
            )
            output = next_output
        audio_options = ["-an"]
        if audio_path is not None:
            audio_input = len(clips)
            audio_output = f"{audio_input}:a:0"
            audio_filters: list[str] = []
            if abs(audio_tempo - 1.0) > 0.0005:
                audio_filters.append(f"atempo={audio_tempo:.6f}")
            if normalize_audio:
                audio_filters.append("loudnorm=I=-16:LRA=11:TP=-1.5")
            if target_duration is not None:
                audio_filters.extend(("apad", f"atrim=duration={target_duration:.6f}", "asetpts=PTS-STARTPTS"))
            elif normalize_audio:
                audio_filters.append("apad=pad_dur=60")
            if audio_filters:
                filters.append(f"[{audio_input}:a]{','.join(audio_filters)}[aout]")
                audio_output = "[aout]"
            audio_options = ["-map", audio_output, "-c:a", self.profile.audio_codec, "-b:a", "192k", "-shortest"]
        duration_options = ["-t", f"{target_duration:.6f}"] if target_duration is not None else []
        return [self.ffmpeg, "-y", *inputs, "-filter_complex", ";".join(filters), "-map", output,
                "-c:v", self.profile.video_codec, "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart",
                "-pix_fmt", "yuv420p", *audio_options, *duration_options, str(destination)]

    def render(
        self,
        clips: list[Path],
        destination: Path,
        hook: str = "",
        audio_path: Path | None = None,
        normalize_audio: bool = True,
        overlays: list[TextOverlay] | None = None,
        audio_tempo: float = 1.0,
        target_duration: float | None = None,
    ) -> Path:
        require_tool(self.ffmpeg); destination.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            self.command(
                clips, destination, hook, audio_path, normalize_audio, overlays,
                audio_tempo=audio_tempo, target_duration=target_duration,
            ),
            capture_output=True,
            text=True,
        )
        if result.returncode: raise RuntimeError(f"render failed: {result.stderr[-1500:]}")
        return destination
