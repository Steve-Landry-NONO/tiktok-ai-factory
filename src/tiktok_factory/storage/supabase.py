"""Supabase REST persistence for complete pipeline genealogy."""

import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from tiktok_factory.domain.models import AgentRun, PipelineResult


class SupabaseRepositoryError(RuntimeError):
    pass


class SupabaseAuthenticationError(SupabaseRepositoryError):
    pass


class SupabaseRepository:
    def __init__(
        self,
        url: str,
        secret_key: str,
        *,
        client: httpx.Client | None = None,
        max_retries: int = 3,
        timeout: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not url or not secret_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
        self._secret_key = secret_key
        self._client = client or httpx.Client(base_url=url.rstrip("/"), timeout=timeout)
        self.max_retries, self._sleep = max_retries, sleep

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._secret_key,
            "Authorization": f"Bearer {self._secret_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        }

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
        self.upsert(
            "storyboards",
            {"id": str(result.storyboard.id), "script_id": str(result.script.id)},
        )
        for shot in result.storyboard.shots:
            row = shot.model_dump(mode="json")
            row.update(
                {
                    "storyboard_id": str(result.storyboard.id),
                    "shot_number": row.pop("number"),
                }
            )
            self.upsert("storyboard_shots", row)
        for job in result.jobs:
            self.upsert("generation_jobs", job)
        for asset in result.assets:
            row = asset.model_dump(mode="json")
            row["storage_key"] = str(row.pop("path"))
            self.upsert("media_assets", row)
        video = result.video.model_dump(mode="json")
        video["storage_key"] = str(video.pop("path"))
        self.upsert("videos", video)
        for review in result.reviews:
            self.upsert("qa_reviews", review)

    def idea_exists(self, idea_id: str) -> bool:
        response = self._request(
            "GET",
            f"/rest/v1/content_ideas?id=eq.{idea_id}&select=id",
        )
        rows = response.json()
        return isinstance(rows, list) and any(
            isinstance(row, dict) and row.get("id") == idea_id for row in rows
        )

    def reserve_orchestration_run(
        self,
        correlation_id: str,
        request: dict[str, Any],
    ) -> bool:
        headers = dict(self._headers)
        headers["Prefer"] = "resolution=ignore-duplicates,return=representation"
        response = self._request(
            "POST",
            "/rest/v1/orchestration_runs?on_conflict=correlation_id",
            headers=headers,
            json={
                "correlation_id": correlation_id,
                "status": "RUNNING",
                "request": request,
            },
        )
        rows = response.json()
        if not isinstance(rows, list):
            raise SupabaseRepositoryError("invalid orchestration reservation response")
        return bool(rows)

    def load_orchestration_run(self, correlation_id: str) -> dict[str, Any] | None:
        encoded = quote(correlation_id, safe="")
        response = self._request(
            "GET",
            f"/rest/v1/orchestration_runs?correlation_id=eq.{encoded}&select=*",
        )
        rows = response.json()
        if not isinstance(rows, list):
            raise SupabaseRepositoryError("invalid orchestration read response")
        for row in rows:
            if isinstance(row, dict):
                return row
        return None

    def complete_orchestration_run(
        self,
        correlation_id: str,
        result: dict[str, Any],
    ) -> None:
        self._patch_orchestration_run(
            correlation_id,
            {
                "status": str(result.get("status") or "COMPLETED"),
                "result": result,
                "error": None,
            },
        )

    def fail_orchestration_run(self, correlation_id: str, error: str) -> None:
        self._patch_orchestration_run(
            correlation_id,
            {"status": "FAILED", "error": error[:500]},
        )

    def load_rerender_metadata(self, idea_id: str) -> dict[str, Any]:
        """Load genealogy only; storage keys are not physical media downloads."""

        def rows(table: str, query: str) -> list[dict[str, Any]]:
            response = self._request("GET", f"/rest/v1/{table}?{query}")
            value = response.json()
            if not isinstance(value, list):
                raise SupabaseRepositoryError(f"invalid {table} metadata response")
            return [row for row in value if isinstance(row, dict)]

        ideas = rows("content_ideas", f"id=eq.{idea_id}&select=*")
        scripts = rows("scripts", f"idea_id=eq.{idea_id}&select=*")
        if not ideas or not scripts:
            raise SupabaseRepositoryError(f"no rerender metadata for idea {idea_id}")
        script = scripts[0]
        boards = rows("storyboards", f"script_id=eq.{script['id']}&select=*")
        if not boards:
            raise SupabaseRepositoryError(f"no storyboard metadata for idea {idea_id}")
        shots = rows(
            "storyboard_shots",
            f"storyboard_id=eq.{boards[0]['id']}&select=*",
        )
        shot_ids = [str(shot["id"]) for shot in shots if "id" in shot]
        jobs: list[dict[str, Any]] = []
        for shot_id in shot_ids:
            jobs.extend(rows("generation_jobs", f"shot_id=eq.{shot_id}&select=*"))
        assets: list[dict[str, Any]] = []
        for job in jobs:
            assets.extend(rows("media_assets", f"job_id=eq.{job['id']}&select=*"))
        if not assets:
            raise SupabaseRepositoryError(f"no media asset metadata for idea {idea_id}")
        return {
            "idea": ideas[0],
            "script": script,
            "storyboard": boards[0],
            "shots": shots,
            "jobs": jobs,
            "assets": assets,
        }

    def _patch_orchestration_run(
        self,
        correlation_id: str,
        values: dict[str, Any],
    ) -> None:
        encoded = quote(correlation_id, safe="")
        payload = dict(values)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        headers = dict(self._headers)
        headers["Prefer"] = "return=representation"
        response = self._request(
            "PATCH",
            f"/rest/v1/orchestration_runs?correlation_id=eq.{encoded}",
            headers=headers,
            json=payload,
        )
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            raise SupabaseRepositoryError("orchestration update did not match a row")

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = kwargs.pop("headers", self._headers)
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.request(
                    method,
                    path,
                    headers=headers,
                    **kwargs,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    raise SupabaseRepositoryError(
                        "Supabase network request failed after retries"
                    ) from exc
                self._sleep(2**attempt)
                continue
            if response.status_code in (401, 403):
                raise SupabaseAuthenticationError("Supabase authentication failed")
            if (
                response.status_code == 429 or response.status_code >= 500
            ) and attempt < self.max_retries:
                self._sleep(2**attempt)
                continue
            if response.is_error:
                raise SupabaseRepositoryError(
                    f"Supabase request failed with status {response.status_code}"
                )
            return response
        raise SupabaseRepositoryError("Supabase request failed after retries")
