import json
from pathlib import Path

import httpx
import pytest

from tiktok_factory.domain.models import StoryboardShot
from tiktok_factory.providers.runway import (
    RunwayAuthenticationError,
    RunwayProvider,
    RunwayTaskError,
)


def test_runway_text_to_video_polls_and_downloads(tmp_path: Path):
    calls: list[tuple[str, str]] = []
    polls = 0
    create_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal polls
        calls.append((request.method, str(request.url)))
        if str(request.url) == "https://api.dev.runwayml.com/v1/text_to_video":
            assert request.headers["authorization"].startswith("Bearer ")
            assert request.headers["x-runway-version"] == "2024-11-06"
            create_payload.update(json.loads(request.content))
            return httpx.Response(200, json={"id": "task-1"})
        if str(request.url) == "https://api.dev.runwayml.com/v1/tasks/task-1":
            polls += 1
            if polls == 1:
                return httpx.Response(200, json={"id": "task-1", "status": "PENDING"})
            return httpx.Response(
                200,
                json={
                    "id": "task-1",
                    "status": "SUCCEEDED",
                    "output": ["https://cdn.example/video.mp4"],
                },
            )
        if str(request.url) == "https://cdn.example/video.mp4":
            assert "authorization" not in request.headers
            return httpx.Response(200, content=b"fake-mp4")
        raise AssertionError(str(request.url))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = RunwayProvider(
        "key-test",
        client=client,
        sleep=lambda _: None,
        jitter=lambda: 0.0,
    )
    shot = StoryboardShot(number=1, concept="Neon city floats upward", caption="Midnight", duration_seconds=7.2)
    destination = tmp_path / "shot.mp4"

    assert provider.generate(shot, destination) == destination
    assert destination.read_bytes() == b"fake-mp4"
    assert create_payload["model"] == "gen4.5"
    assert create_payload["ratio"] == "720:1280"
    assert create_payload["duration"] == 8
    assert "no watermark" in create_payload["promptText"]
    assert polls == 2
    assert len(calls) == 4


def test_runway_cost_uses_normalized_billable_duration():
    provider = RunwayProvider("key-test", sleep=lambda _: None)
    short = StoryboardShot(number=1, concept="x", duration_seconds=1)
    long = StoryboardShot(number=2, concept="x", duration_seconds=12)
    assert provider.normalized_duration(1) == 2
    assert provider.normalized_duration(12) == 10
    assert provider.estimate_cost(short) == pytest.approx(0.24)
    assert provider.estimate_cost(long) == pytest.approx(1.20)


def test_runway_401_is_not_retried(tmp_path: Path):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={})

    provider = RunwayProvider(
        "bad-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
        jitter=lambda: 0.0,
    )
    with pytest.raises(RunwayAuthenticationError, match="authentication failed"):
        provider.generate(StoryboardShot(number=1, concept="x", duration_seconds=2), tmp_path / "x.mp4")
    assert calls == 1


def test_runway_429_retries_creation(tmp_path: Path):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if str(request.url).endswith("/v1/text_to_video"):
            calls += 1
            if calls == 1:
                return httpx.Response(429, json={})
            return httpx.Response(200, json={"id": "task-1"})
        if str(request.url).endswith("/v1/tasks/task-1"):
            return httpx.Response(200, json={"status": "SUCCEEDED", "output": ["https://cdn.example/v.mp4"]})
        return httpx.Response(200, content=b"video")

    provider = RunwayProvider(
        "key-test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
        jitter=lambda: 0.0,
    )
    provider.generate(StoryboardShot(number=1, concept="x", duration_seconds=2), tmp_path / "x.mp4")
    assert calls == 2


def test_runway_terminal_task_failure_is_explicit(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/v1/text_to_video"):
            return httpx.Response(200, json={"id": "task-1"})
        return httpx.Response(200, json={"status": "FAILED", "failureCode": "SAFETY.INPUT.TEXT"})

    provider = RunwayProvider(
        "key-test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
        jitter=lambda: 0.0,
    )
    with pytest.raises(RunwayTaskError, match="SAFETY.INPUT.TEXT"):
        provider.generate(StoryboardShot(number=1, concept="x", duration_seconds=2), tmp_path / "x.mp4")
