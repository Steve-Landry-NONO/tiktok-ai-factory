from pathlib import Path

from fastapi.testclient import TestClient

from tiktok_factory.api.app import create_app
from tiktok_factory.api.service import FactoryOrchestrationService, RunRequest, RunResponse


def test_health_and_bearer_auth(tmp_path: Path) -> None:
    def runner(request: RunRequest, output_dir: Path) -> RunResponse:
        assert output_dir == tmp_path / request.correlation_id
        return RunResponse(
            correlation_id=request.correlation_id,
            status="READY_TO_PUBLISH",
            final_video="output/final.mp4",
        )

    service = FactoryOrchestrationService(runner=runner, output_root=tmp_path)
    client = TestClient(create_app(service, api_token="test-token"))

    assert client.get("/healthz").json()["status"] == "ok"
    unauthorized = client.post(
        "/v1/runs",
        json={
            "idea": "A safe test idea",
            "correlation_id": "test-run-1",
            "mode": "mock",
            "video_provider": "synthetic",
            "postprocess": False,
        },
    )
    assert unauthorized.status_code == 401

    response = client.post(
        "/v1/runs",
        headers={"Authorization": "Bearer test-token"},
        json={
            "idea": "A safe test idea",
            "correlation_id": "test-run-1",
            "mode": "mock",
            "video_provider": "synthetic",
            "postprocess": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "READY_TO_PUBLISH"


def test_missing_api_token_fails_closed(tmp_path: Path) -> None:
    service = FactoryOrchestrationService(
        runner=lambda request, output: RunResponse(
            correlation_id=request.correlation_id,
            status="READY_TO_PUBLISH",
        ),
        output_root=tmp_path,
    )
    client = TestClient(create_app(service, api_token=""))
    response = client.post(
        "/v1/runs",
        headers={"Authorization": "Bearer anything"},
        json={
            "idea": "A safe test idea",
            "correlation_id": "test-run-2",
            "mode": "mock",
            "video_provider": "synthetic",
            "postprocess": False,
        },
    )
    assert response.status_code == 503
