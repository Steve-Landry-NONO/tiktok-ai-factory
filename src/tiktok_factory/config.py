from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings; secrets are read only from the environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    max_cost_per_video: float = Field(10.0, ge=0)
    max_daily_generation_cost: float = Field(100.0, ge=0)
    max_retries: int = Field(3, ge=0, le=10)
    output_dir: Path = Path("output")
    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
    llm_provider: str = "groq"
    groq_api_key: str | None = None
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    groq_primary_model: str = "openai/gpt-oss-120b"
    groq_judge_model: str = "openai/gpt-oss-20b"
