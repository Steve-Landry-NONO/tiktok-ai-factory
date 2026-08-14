import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from tiktok_factory.providers.local import require_tool


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
    ) -> list[str]:
        if not clips: raise ValueError("at least one clip is required")
        inputs = [item for clip in clips for item in ("-i", str(clip))]
        if audio_path is not None:
            inputs.extend(("-i", str(audio_path)))
        filters = []
        for i in range(len(clips)):
            filters.append(f"[{i}:v]scale={self.profile.width}:{self.profile.height}:force_original_aspect_ratio=decrease,"
                           f"pad={self.profile.width}:{self.profile.height}:(ow-iw)/2:(oh-ih)/2,fps={self.profile.fps},"
                           f"setsar=1,format=yuv420p[v{i}]")
        filters.append("".join(f"[v{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=0[vcat]")
        output = "[vcat]"
        if hook:
            safe = hook.replace("'", "’").replace(":", "\\:")
            filters.append(f"[vcat]drawtext=text='{safe}':fontcolor=white:fontsize=64:x=(w-text_w)/2:y=180:"
                           "box=1:boxcolor=black@0.6:boxborderw=20[vout]")
            output = "[vout]"
        audio_options = ["-an"]
        if audio_path is not None:
            audio_input = len(clips)
            audio_output = f"{audio_input}:a:0"
            if normalize_audio:
                filters.append(f"[{audio_input}:a]loudnorm=I=-16:LRA=11:TP=-1.5[aout]")
                audio_output = "[aout]"
            audio_options = ["-map", audio_output, "-c:a", self.profile.audio_codec, "-b:a", "192k", "-shortest"]
        return [self.ffmpeg, "-y", *inputs, "-filter_complex", ";".join(filters), "-map", output,
                "-c:v", self.profile.video_codec, "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart",
                "-pix_fmt", "yuv420p", *audio_options, str(destination)]

    def render(
        self,
        clips: list[Path],
        destination: Path,
        hook: str = "",
        audio_path: Path | None = None,
        normalize_audio: bool = True,
    ) -> Path:
        require_tool(self.ffmpeg); destination.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            self.command(clips, destination, hook, audio_path, normalize_audio),
            capture_output=True,
            text=True,
        )
        if result.returncode: raise RuntimeError(f"render failed: {result.stderr[-1500:]}")
        return destination
