import json
from pathlib import Path
from typing import Any

import pytest

from tiktok_factory.api.service import FactoryOrchestrationService, RunRequest, RunResponse


class FakeRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def reserve_orchestration_run(self, correlation_id: str, request: dict[str, Any]) -> bool:
        if correlation_id in self.rows:
            return False
        self.rows[correlation_id] = {
            "correlation_id": correlation_id,
            "status": "RUNNING",
            "request": request,
            "result": None,
        }
        return True

    def load_orchestration_run(self, correlation_id: str) -> dict[str, Any] | None:
        return self.rows.get(correlation_id)

    def complete_orchestration_run(self, correlation_id: str, result: dict[str, Any]) -> None:
        self.rows[correlation_id]["status"] = str(result["status"])
        self.rows[correlation_id]["result"] = result

    def fail_orchestration_run(self, correlation_id: str, error: str) -> None:
        self.rows[correlation_id]["status"] = "FAILED"
        self.rows[correlation_id]["error"] = error


def test_duplicate_correlation_id_replays_without_rerunning(tmp_path: Path) -> None:
    repository = FakeRepository()
    calls = 0

    def runner(request: RunRequest, output_dir: Path) -> RunResponse:
        nonlocal calls
        calls += 1
        return RunResponse(
            correlation_id=request.correlation_id,
            status="READY_TO_PUBLISH",
            final_video=str(output_dir / "postprocessed" / "final.mp4"),
        )

    service = FactoryOrchestrationService(
        runner=runner,
        repository=repository,
        output_root=tmp_path,
    )
    request = RunRequest(
        idea="A safe futuristic city concept",
        correlation_id="daily-2026-08-14-slot-1",
        mode="live",
        video_provider="runway",
        postprocess=True,
    )

    first = service.run(request)
    second = service.run(request)

    assert calls == 1
    assert first.replayed is False
    assert second.replayed is True
    assert second.final_video == first.final_video


def test_lightweight_mock_avoids_pipeline_and_paid_providers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FACTORY_API_LIGHTWEIGHT_MOCK", "1")

    def fail_if_pipeline_is_built(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("full media pipeline must not run in lightweight mock mode")

    monkeypatch.setattr(
        "tiktok_factory.api.service.build_intelligent_pipeline",
        fail_if_pipeline_is_built,
    )

    service = FactoryOrchestrationService(output_root=tmp_path)
    response = service.run(
        RunRequest(
            idea="A safe futuristic city concept",
            correlation_id="n8n-mock-123",
            mode="mock",
            video_provider="synthetic",
            postprocess=False,
        )
    )

    assert response.status == "MOCK_OK"
    assert response.video_provider == "synthetic"
    assert response.estimated_generation_cost_usd == 0.0
    assert response.final_video is None
    assert response.generation_metadata is not None

    metadata = json.loads(Path(response.generation_metadata).read_text(encoding="utf-8"))
    assert metadata["paid_provider_calls"] == 0
    assert metadata["ffmpeg_calls"] == 0
