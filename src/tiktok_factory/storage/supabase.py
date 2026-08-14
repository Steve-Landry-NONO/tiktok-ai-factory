"""Supabase REST persistence for complete pipeline genealogy."""
import time
from collections.abc import Callable
from typing import Any
import httpx
from pydantic import BaseModel
from tiktok_factory.domain.models import AgentRun, PipelineResult

class SupabaseRepositoryError(RuntimeError): pass
class SupabaseAuthenticationError(SupabaseRepositoryError): pass

class SupabaseRepository:
    def __init__(self, url: str, secret_key: str, *, client: httpx.Client | None = None,
                 max_retries: int = 3, timeout: float = 30.0,
                 sleep: Callable[[float], None] = time.sleep):
        if not url or not secret_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
        self._secret_key = secret_key
        self._client = client or httpx.Client(base_url=url.rstrip("/"), timeout=timeout)
        self.max_retries, self._sleep = max_retries, sleep

    @property
    def _headers(self) -> dict[str, str]:
        return {"apikey": self._secret_key, "Authorization": f"Bearer {self._secret_key}",
                "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=representation"}

    def upsert(self, table: str, value: BaseModel | dict[str, Any]) -> dict[str, Any]:
        payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        response = self._request("POST", f"/rest/v1/{table}?on_conflict=id", json=payload)
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise SupabaseRepositoryError("Supabase returned an invalid representation")
        return rows[0]

    def save_agent_run(self, run: AgentRun, model: str) -> None:
        payload = run.model_dump(mode="json")
        payload["output"] = {"model": model, "data": payload["output"]}
        self.upsert("agent_runs", payload)

    def persist_pipeline(self, result: PipelineResult, correlation_id: str) -> None:
        idea = result.idea.model_dump(mode="json")
        idea.update({"viral_score": result.viral_score.total, "correlation_id": correlation_id})
        self.upsert("content_ideas", idea)
        self.upsert("scripts", result.script)
        self.upsert("storyboards", {"id": str(result.storyboard.id), "script_id": str(result.script.id)})
        for shot in result.storyboard.shots:
            row = shot.model_dump(mode="json")
            row.update({"storyboard_id": str(result.storyboard.id), "shot_number": row.pop("number")})
            self.upsert("storyboard_shots", row)
        for job in result.jobs: self.upsert("generation_jobs", job)
        for asset in result.assets:
            row = asset.model_dump(mode="json"); row["storage_key"] = str(row.pop("path"))
            self.upsert("media_assets", row)
        video = result.video.model_dump(mode="json"); video["storage_key"] = str(video.pop("path"))
        self.upsert("videos", video)
        for review in result.reviews: self.upsert("qa_reviews", review)

    def idea_exists(self, idea_id: str) -> bool:
        response = self._request("GET", f"/rest/v1/content_ideas?id=eq.{idea_id}&select=id")
        rows = response.json()
        return isinstance(rows, list) and any(isinstance(row, dict) and row.get("id") == idea_id for row in rows)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            try: response = self._client.request(method, path, headers=self._headers, **kwargs)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    raise SupabaseRepositoryError("Supabase network request failed after retries") from exc
                self._sleep(2**attempt); continue
            if response.status_code in (401, 403):
                raise SupabaseAuthenticationError("Supabase authentication failed")
            if (response.status_code == 429 or response.status_code >= 500) and attempt < self.max_retries:
                self._sleep(2**attempt); continue
            if response.is_error:
                raise SupabaseRepositoryError(f"Supabase request failed with status {response.status_code}")
            return response
        raise SupabaseRepositoryError("Supabase request failed after retries")
