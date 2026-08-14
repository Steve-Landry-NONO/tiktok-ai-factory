import shutil
import subprocess
from pathlib import Path
from typing import Any
from uuid import UUID

from tiktok_factory.domain.models import PerformanceMetric, StoryboardShot
from tiktok_factory.providers.base import AnalyticsProvider, LLMProvider, StorageProvider, VideoGenerationProvider


class ToolUnavailableError(RuntimeError): pass
class ProviderNotConfiguredError(RuntimeError): pass


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path: raise ToolUnavailableError(f"Required executable not found: {name}")
    return path


class MockLLMProvider(LLMProvider):
    def __init__(self, response: dict[str, Any]): self.response = response
    def structured(self, prompt: str, schema: type[Any]) -> Any:
        del prompt
        return schema.model_validate(self.response)


class SyntheticVideoProvider(VideoGenerationProvider):
    name, model, estimated_cost = "local", "ffmpeg-synthetic-v1", 0.0
    def __init__(self, ffmpeg: str = "ffmpeg", width: int = 1080, height: int = 1920, fps: int = 30):
        self.ffmpeg, self.width, self.height, self.fps = ffmpeg, width, height, fps

    def command(self, shot: StoryboardShot, destination: Path) -> list[str]:
        text = f"Shot {shot.number}: {shot.concept}".replace("'", "’").replace(":", "\\:")
        vf = (f"drawtext=text='{text}':fontcolor=white:fontsize=52:"
              "x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@0.55:boxborderw=25")
        return [self.ffmpeg, "-y", "-f", "lavfi", "-i",
                f"color=c=0x182848:s={self.width}x{self.height}:r={self.fps}:d={shot.duration_seconds}",
                "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(destination)]

    def generate(self, shot: StoryboardShot, destination: Path) -> Path:
        require_tool(self.ffmpeg); destination.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(self.command(shot, destination), capture_output=True, text=True)
        if result.returncode: raise RuntimeError(f"Synthetic generation failed: {result.stderr[-1000:]}")
        return destination


class LocalStorageProvider(StorageProvider):
    def __init__(self, root: Path): self.root = root
    def put(self, source: Path, key: str) -> Path:
        target = self.root / key; target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target.resolve(): shutil.copy2(source, target)
        return target


class MockAnalyticsProvider(AnalyticsProvider):
    def metrics(self, publication_id: UUID) -> PerformanceMetric:
        return PerformanceMetric(publication_id=publication_id, views=1000, likes=120, comments=15,
            shares=20, average_watch_time=8.4, completion_rate=.72, followers_gained=9)


class OpenAIAdapter(LLMProvider):
    def structured(self, prompt: str, schema: type[Any]) -> Any:
        raise ProviderNotConfiguredError("Connect the verified OpenAI SDK and structured-output API")


class RunwayAdapter(VideoGenerationProvider):
    name, model, estimated_cost = "runway", "configure-model", 0.0
    def generate(self, shot: StoryboardShot, destination: Path) -> Path:
        raise ProviderNotConfiguredError("Configure against current Runway documentation")
