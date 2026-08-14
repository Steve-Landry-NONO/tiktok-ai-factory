import json

import httpx

from tiktok_factory.storage.supabase import SupabaseRepository


def make_repository(handler):
    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://project.supabase.co",
    )
    return SupabaseRepository(
        "https://project.supabase.co",
        "fake-server-secret",
        client=client,
        sleep=lambda delay: None,
    )


def test_orchestration_reservation_uses_ignore_duplicates() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content)
        return httpx.Response(201, json=[payload])

    repository = make_repository(handler)
    claimed = repository.reserve_orchestration_run(
        "daily-2026-08-14-slot-1",
        {"idea": "safe"},
    )

    assert claimed is True
    assert "resolution=ignore-duplicates" in requests[0].headers["prefer"]
    assert json.loads(requests[0].content)["status"] == "RUNNING"


def test_duplicate_orchestration_reservation_returns_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json=[])

    repository = make_repository(handler)
    assert repository.reserve_orchestration_run("same-run", {"idea": "safe"}) is False


def test_complete_orchestration_run_patches_result() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            json=[{"correlation_id": "same-run", **payload}],
        )

    repository = make_repository(handler)
    repository.complete_orchestration_run(
        "same-run",
        {"correlation_id": "same-run", "status": "READY_TO_PUBLISH"},
    )

    assert requests[0].method == "PATCH"
    payload = json.loads(requests[0].content)
    assert payload["status"] == "READY_TO_PUBLISH"
    assert payload["result"]["correlation_id"] == "same-run"
