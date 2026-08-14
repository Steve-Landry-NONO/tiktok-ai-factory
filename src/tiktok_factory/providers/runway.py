"""Runway text-to-video provider using the documented asynchronous task API."""
from __future__ import annotations

import math
import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from tiktok_factory.domain.models import StoryboardShot
from tiktok_factory.providers.base import VideoGenerationProvider


class RunwayProviderError(RuntimeError):
    """Base sanitized Runway error."""


class RunwayAuthenticationError(RunwayProviderError):
    pass


class RunwayTaskError(RunwayProviderError):
    pass


class RunwayProvider(VideoGenerationProvider):
    """Generate one portrait clip per storyboard shot with Runway Gen-4.5.

    The provider uses POST /v1/text_to_video, polls GET /v1/tasks/{id}, and
    immediately downloads the ephemeral output URL to local durable storage.
    """

    name = "runway"
    estimated_cost = 0.0
    api_version = "2024-11-06"
    base_url = "https://api.dev.runwayml.com"
    credit_usd = 0.01

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gen4.5",
        ratio: str = "720:1280",
        credits_per_second: float = 12.0,
        client: httpx.Client | None = None,
        max_retries: int = 3,
        poll_interval: float = 5.0,
        timeout_seconds: float = 600.0,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = lambda: random.uniform(0.0, 1.0),
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not api_key:
            raise ValueError("Runway API key is required")
        self.api_key = api_key
        self.model = model
        self.ratio = ratio
        self.credits_per_second = credits_per_second
        self.max_retries = max_retries
        self.poll_interval = max(5.0, poll_interval)
        self.timeout_seconds = timeout_seconds
        self.sleep = sleep
        self.jitter = jitter
        self.monotonic = monotonic
        self._client = client or httpx.Client(timeout=60.0, follow_redirects=True)

    @staticmethod
    def normalized_duration(seconds: float) -> int:
        """Runway Gen-4.5 accepts integer durations from 2 through 10 seconds."""
        return min(10, max(2, int(math.ceil(seconds))))

    def estimate_cost(self, shot: StoryboardShot) -> float:
        credits = self.normalized_duration(shot.duration_seconds) * self.credits_per_second
        return round(credits * self.credit_usd, 4)

    def generate(self, shot: StoryboardShot, destination: Path) -> Path:
        duration = self.normalized_duration(shot.duration_seconds)
        task = self._api_request(
            "POST",
            "/v1/text_to_video",
            json={
                "model": self.model,
                "promptText": self._prompt(shot),
                "ratio": self.ratio,
                "duration": duration,
            },
        )
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise RunwayProviderError("Runway task creation returned no task id")

        output_url = self._wait_for_output(task_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._download(output_url, destination)
        if not destination.exists() or destination.stat().st_size == 0:
            raise RunwayProviderError("Runway output download produced an empty file")
        return destination

    def _prompt(self, shot: StoryboardShot) -> str:
        prompt = (
            f"{shot.concept}. {shot.caption}. "
            "Vertical cinematic video, coherent natural motion, visually striking first second, "
            "single clear action, realistic lighting, smooth camera movement, no on-screen text, "
            "no subtitles, no watermark, no logo."
        )
        return prompt[:1000]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": self.api_version,
        }

    def _api_request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.request(method, url, headers=self._headers(), **kwargs)
            except httpx.RequestError as exc:
                if attempt >= self.max_retries:
                    raise RunwayProviderError("Runway network request failed after retries") from exc
                self._backoff(attempt)
                continue

            if response.status_code in (401, 403):
                raise RunwayAuthenticationError("Runway authentication failed")
            if response.status_code == 429 or response.status_code >= 500:
                if attempt >= self.max_retries:
                    raise RunwayProviderError(
                        f"Runway transient HTTP {response.status_code} persisted after retries"
                    )
                self._backoff(attempt)
                continue
            if response.status_code >= 400:
                raise RunwayProviderError(f"Runway request rejected with HTTP {response.status_code}")
            try:
                data = response.json()
            except ValueError as exc:
                raise RunwayProviderError("Runway returned invalid JSON") from exc
            if not isinstance(data, dict):
                raise RunwayProviderError("Runway returned an unexpected response shape")
            return data
        raise AssertionError("unreachable")

    def _wait_for_output(self, task_id: str) -> str:
        deadline = self.monotonic() + self.timeout_seconds
        while self.monotonic() < deadline:
            task = self._api_request("GET", f"/v1/tasks/{task_id}")
            status = task.get("status")
            if status == "SUCCEEDED":
                output = task.get("output")
                if isinstance(output, list) and output and isinstance(output[0], str):
                    return output[0]
                raise RunwayTaskError("Runway task succeeded without an output URL")
            if status in ("FAILED", "CANCELED"):
                failure_code = task.get("failureCode")
                suffix = f" ({failure_code})" if isinstance(failure_code, str) else ""
                raise RunwayTaskError(f"Runway task ended with status {status}{suffix}")
            self.sleep(self.poll_interval + max(0.0, self.jitter()))
        raise RunwayTaskError("Runway task polling timed out")

    def _download(self, url: str, destination: Path) -> None:
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.get(url, follow_redirects=True)
            except httpx.RequestError as exc:
                if attempt >= self.max_retries:
                    raise RunwayProviderError("Runway output download failed after retries") from exc
                self._backoff(attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt >= self.max_retries:
                    raise RunwayProviderError("Runway output download failed after retries")
                self._backoff(attempt)
                continue
            if response.status_code >= 400:
                raise RunwayProviderError(
                    f"Runway output download rejected with HTTP {response.status_code}"
                )
            destination.write_bytes(response.content)
            return
        raise AssertionError("unreachable")

    def _backoff(self, attempt: int) -> None:
        self.sleep(min(30.0, (2**attempt) + max(0.0, self.jitter())))
