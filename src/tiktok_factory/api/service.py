from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from tiktok_factory.cli.__main__ import build_intelligent_pipeline
from tiktok_factory.pipeline.rerender import ExistingClipsRerenderer
from tiktok_factory.providers.groq_tts import (
    DEFAULT_ORPHEUS_VOICE,
    ORPHEUS_ENGLISH_MODEL,
    GroqTextToSpeech,
)
from tiktok_factory.storage.supabase import SupabaseRepository


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idea: str = Field(min_length=3, max_length=1000)
    correlation_id: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    mode: Literal["mock", "live"] = "live"
    video_provider: Literal["synthetic", "runway"] = "runway"
    postprocess: bool = True


class RunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    status: str
    replayed: bool = False
    idea_id: str | None = None
    viral_score: float | None = None
    llm_calls: int | None = None
    video_provider: str | None = None
    estimated_generation_cost_usd: float | None = None
    final_video: str | None = None
    generation_metadata: str | None = None
    postprocess_metadata: str | None = None


class OrchestrationRepository(Protocol):
    def reserve_orchestration_run(self, correlation_id: str, request: dict[str, Any]) -> bool: ...

    def load_orchestration_run(self, correlation_id: str) -> dict[str, Any] | None: ...

    def complete_orchestration_run(self, correlation_id: str, result: dict[str, Any]) -> None: ...

    def fail_orchestration_run(self, correlation_id: str, error: str) -> None: ...


Runner = Callable[[RunRequest, Path], RunResponse]


class FactoryOrchestrationService:
    """Synchronous control-plane service intended to be called by n8n.

    A Supabase reservation is acquired before any live LLM or Runway work. Replays
    with the same correlation_id therefore do not duplicate paid generation.
    """

    def __init__(
        self,
        *,
        runner: Runner | None = None,
        repository: OrchestrationRepository | None = None,
        output_root: Path | None = None,
    ) -> None:
        self._runner = runner or _run_pipeline
        self._repository = repository
        self._output_root = output_root or Path(os.getenv("FACTORY_OUTPUT_ROOT", "output/api"))

    def run(self, request: RunRequest) -> RunResponse:
        repository = self._repository or self._repository_from_env(request)
        request_payload = request.model_dump(mode="json")

        if repository is not None:
            claimed = repository.reserve_orchestration_run(
                request.correlation_id,
                request_payload,
            )
            if not claimed:
                existing = repository.load_orchestration_run(request.correlation_id)
                if existing is None:
                    raise RuntimeError("orchestration reservation exists but cannot be read back")
                return self._response_from_existing(request.correlation_id, existing)

        output_dir = self._output_root / request.correlation_id
        try:
            response = self._runner(request, output_dir)
        except Exception as exc:
            if repository is not None:
                repository.fail_orchestration_run(request.correlation_id, str(exc)[:500])
            raise

        if repository is not None:
            repository.complete_orchestration_run(
                request.correlation_id,
                response.model_dump(mode="json"),
            )
        return response

    @staticmethod
    def _repository_from_env(request: RunRequest) -> OrchestrationRepository | None:
        if request.mode != "live":
            return None
        url = os.getenv("SUPABASE_URL")
        secret = os.getenv("SUPABASE_SECRET_KEY")
        if not url or not secret:
            raise RuntimeError(
                "live orchestration requires SUPABASE_URL and SUPABASE_SECRET_KEY"
            )
        return SupabaseRepository(url, secret)

    @staticmethod
    def _response_from_existing(
        correlation_id: str,
        row: dict[str, Any],
    ) -> RunResponse:
        result = row.get("result")
        if isinstance(result, dict):
            payload = dict(result)
            payload["replayed"] = True
            return RunResponse.model_validate(payload)
        return RunResponse(
            correlation_id=correlation_id,
            status=str(row.get("status") or "RUNNING"),
            replayed=True,
        )


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _run_lightweight_mock(request: RunRequest, output_dir: Path) -> RunResponse:
    """Validate the remote control plane without invoking FFmpeg or paid providers."""

    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / "mock-control-plane.json"
    metadata_path.write_text(
        json.dumps(
            {
                "correlation_id": request.correlation_id,
                "idea": request.idea,
                "mode": request.mode,
                "video_provider": request.video_provider,
                "postprocess": request.postprocess,
                "status": "MOCK_OK",
                "paid_provider_calls": 0,
                "ffmpeg_calls": 0,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return RunResponse(
        correlation_id=request.correlation_id,
        status="MOCK_OK",
        video_provider=request.video_provider,
        estimated_generation_cost_usd=0.0,
        generation_metadata=str(metadata_path),
    )


def _run_pipeline(request: RunRequest, output_dir: Path) -> RunResponse:
    if request.video_provider == "runway" and request.mode != "live":
        raise ValueError("Runway is available only in live mode")

    if (
        request.mode == "mock"
        and request.video_provider == "synthetic"
        and _env_flag("FACTORY_API_LIGHTWEIGHT_MOCK")
    ):
        return _run_lightweight_mock(request, output_dir)

    pipeline = build_intelligent_pipeline(request.mode, request.video_provider)
    result = pipeline.run(request.idea, output_dir, request.correlation_id)
    final_video = result.video.path
    postprocess_metadata: Path | None = None

    if request.postprocess and result.status.value == "READY_TO_PUBLISH":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("post-processing narration requires GROQ_API_KEY")
        rerender = ExistingClipsRerenderer(
            GroqTextToSpeech(
                api_key,
                model=os.getenv("GROQ_TTS_MODEL", ORPHEUS_ENGLISH_MODEL),
                voice=os.getenv("GROQ_TTS_VOICE", DEFAULT_ORPHEUS_VOICE),
            )
        ).run(output_dir, result.metadata_path, output_dir / "postprocessed")
        final_video = rerender.video
        postprocess_metadata = rerender.metadata

    status = "READY_TO_PUBLISH" if postprocess_metadata is not None else result.status.value
    return RunResponse(
        correlation_id=request.correlation_id,
        status=status,
        idea_id=str(result.idea.id),
        viral_score=result.viral_score.total,
        llm_calls=len(pipeline.agent_runs),
        video_provider=request.video_provider,
        estimated_generation_cost_usd=round(
            sum(job.estimated_cost for job in result.jobs),
            4,
        ),
        final_video=str(final_video),
        generation_metadata=str(result.metadata_path),
        postprocess_metadata=(
            str(postprocess_metadata) if postprocess_metadata is not None else None
        ),
    )
