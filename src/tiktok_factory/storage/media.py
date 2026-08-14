"""Physical media backends, deliberately separate from metadata repositories."""

from __future__ import annotations

import mimetypes
import shutil
import time
from pathlib import Path, PurePosixPath
from typing import Protocol
from urllib.parse import quote

import httpx


class MediaStorage(Protocol):
    """Store and materialize physical media objects."""

    def put(self, source: Path, key: str, content_type: str | None = None) -> str: ...

    def materialize(self, key: str, destination: Path) -> Path: ...


class LocalMediaStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def put(self, source: Path, key: str, content_type: str | None = None) -> str:
        del content_type
        target = (self.root / _safe_key(key)).resolve()
        if self.root not in target.parents and target != self.root:
            raise ValueError("media key escapes storage root")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target:
            shutil.copy2(source, target)
        return _safe_key(key)

    def materialize(self, key: str, destination: Path) -> Path:
        source = (self.root / _safe_key(key)).resolve()
        if self.root not in source.parents and source != self.root:
            raise ValueError("media key escapes storage root")
        if not source.is_file():
            raise FileNotFoundError(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination


class SupabaseMediaStorage:
    """Private Supabase Storage backend using the server-side secret key."""

    def __init__(
        self,
        base_url: str,
        secret_key: str,
        *,
        bucket: str = "tiktok-media",
        client: httpx.Client | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("Supabase media storage requires an https URL")
        if not secret_key:
            raise ValueError("Supabase media storage requires a secret key")
        self.base_url = base_url.rstrip("/")
        self.secret_key = secret_key
        self.bucket = _safe_key(bucket)
        self.client = client or httpx.Client(timeout=timeout)
        self.max_retries = max(1, max_retries)

    def put(self, source: Path, key: str, content_type: str | None = None) -> str:
        if not source.is_file():
            raise FileNotFoundError(source)
        safe_key = _safe_key(key)
        media_type = content_type or _content_type(source)
        url = self._object_url(safe_key)
        headers = {
            **self._auth_headers(),
            "content-type": media_type,
            "cache-control": "3600",
            "x-upsert": "false",
        }
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with source.open("rb") as handle:
                    response = self.client.post(url, headers=headers, content=handle)
                if response.status_code in {200, 201}:
                    return safe_key
                if response.status_code in {400, 409} and "exist" in response.text.lower():
                    return safe_key
                if response.status_code == 429 or response.status_code >= 500:
                    raise RuntimeError(
                        f"Supabase Storage upload temporary failure: HTTP {response.status_code}"
                    )
                raise RuntimeError(
                    f"Supabase Storage upload failed: HTTP {response.status_code} "
                    f"{response.text[:300]}"
                )
            except (httpx.HTTPError, RuntimeError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(min(2 ** (attempt - 1), 4))
        raise RuntimeError(f"Supabase Storage upload failed after retries: {last_error}")

    def materialize(self, key: str, destination: Path) -> Path:
        safe_key = _safe_key(key)
        encoded = quote(safe_key, safe="/")
        url = (
            f"{self.base_url}/storage/v1/object/authenticated/"
            f"{quote(self.bucket, safe='')}/{encoded}"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.client.stream("GET", url, headers=self._auth_headers()) as response:
            if response.status_code != 200:
                raise RuntimeError(
                    f"Supabase Storage download failed: HTTP {response.status_code} "
                    f"{response.text[:300]}"
                )
            with destination.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
        return destination

    def _object_url(self, key: str) -> str:
        encoded = quote(key, safe="/")
        return f"{self.base_url}/storage/v1/object/{quote(self.bucket, safe='')}/{encoded}"

    def _auth_headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self.secret_key}",
            "apikey": self.secret_key,
        }


class GitHubArtifactMediaStorage:
    """Future artifact downloader; CI should currently download/extract first."""

    def put(self, source: Path, key: str, content_type: str | None = None) -> str:
        del source, key, content_type
        raise NotImplementedError("GitHub artifacts are not a durable production media store")

    def materialize(self, key: str, destination: Path) -> Path:
        del key, destination
        raise NotImplementedError("download the GitHub artifact before rerendering")


def persist_directory(storage: MediaStorage, root: Path, prefix: str) -> list[str]:
    """Upload supported output files below root using immutable correlation-scoped keys."""

    if not root.is_dir():
        raise FileNotFoundError(root)
    safe_prefix = _safe_key(prefix)
    uploaded: list[str] = []
    for source in sorted(path for path in root.rglob("*") if path.is_file()):
        if source.suffix.lower() not in {".mp4", ".wav", ".png", ".json"}:
            continue
        relative = source.relative_to(root).as_posix()
        key = f"{safe_prefix}/{relative}"
        uploaded.append(storage.put(source, key, _content_type(source)))
    return uploaded


def _content_type(path: Path) -> str:
    overrides = {
        ".mp4": "video/mp4",
        ".wav": "audio/wav",
        ".png": "image/png",
        ".json": "application/json",
    }
    return overrides.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _safe_key(key: str) -> str:
    candidate = PurePosixPath(key.strip("/"))
    if not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError("invalid media storage key")
    return candidate.as_posix()
