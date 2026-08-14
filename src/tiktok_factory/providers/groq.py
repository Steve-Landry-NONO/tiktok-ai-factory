"""Groq OpenAI-compatible structured-output provider."""

import json
import time
from collections.abc import Callable
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMProviderError(RuntimeError):
    """Base sanitized LLM failure."""


class LLMAuthenticationError(LLMProviderError):
    pass


class LLMRateLimitError(LLMProviderError):
    pass


class LLMResponseError(LLMProviderError):
    pass


class GroqProvider:
    name = "groq"
    base_url = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.Client | None = None,
        max_retries: int = 3,
        timeout: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not api_key:
            raise ValueError("GROQ_API_KEY is required")
        self._api_key = api_key
        self._client = client or httpx.Client(base_url=self.base_url, timeout=timeout)
        self.max_retries = max_retries
        self._sleep = sleep
        self.call_count = 0

    def structured(self, agent: str, prompt: str, schema: type[T], model: str) -> T:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Return only data matching the supplied strict schema."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": agent.replace("-", "_").lower(),
                    "strict": True,
                    "schema": schema.model_json_schema(),
                },
            },
        }
        response = self._post_with_retry(payload)
        try:
            message = response.json()["choices"][0]["message"]
            if message.get("refusal"):
                raise LLMResponseError("model refused the structured request")
            content = message["content"]
            parsed = content if isinstance(content, dict) else json.loads(content)
            return schema.model_validate(parsed)
        except LLMResponseError:
            raise
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise LLMResponseError("invalid structured response from LLM") from exc

    def _post_with_retry(self, payload: dict[str, object]) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            self.call_count += 1
            try:
                response = self._client.post(
                    "/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    raise LLMProviderError("LLM network request failed after retries") from exc
                self._sleep(2**attempt)
                continue
            if response.status_code == 401:
                raise LLMAuthenticationError("LLM authentication failed")
            if response.status_code == 429 or response.status_code >= 500:
                if attempt >= self.max_retries:
                    if response.status_code == 429:
                        raise LLMRateLimitError("LLM rate limit exceeded after retries")
                    raise LLMProviderError("LLM service failed after retries")
                self._sleep(2**attempt)
                continue
            if response.is_error:
                raise LLMProviderError(f"LLM request failed with status {response.status_code}")
            return response
        raise AssertionError("bounded retry loop exhausted unexpectedly")
