from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore[import-not-found]


class Settings(BaseSettings):  # type: ignore[misc]
    """Runtime settings; secrets are read only from the environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    max_cost_per_video: float = Field(10.0, ge=0)
    max_daily_generation_cost: float = Field(100.0, ge=0)
    max_retries: int = Field(3, ge=0, le=10)
    output_dir: Path = Path("output")
    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
