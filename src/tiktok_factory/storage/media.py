"""Physical media backends, deliberately separate from metadata repositories."""

import shutil
from pathlib import Path
from typing import Protocol


class MediaStorage(Protocol):
    """Materialize a physical media object as a local file."""

    def materialize(self, key: str, destination: Path) -> Path: ...


class LocalMediaStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def materialize(self, key: str, destination: Path) -> Path:
        source = (self.root / key).resolve()
        if self.root not in source.parents and source != self.root:
            raise ValueError("media key escapes storage root")
        if not source.is_file():
            raise FileNotFoundError(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination


class SupabaseMediaStorage:
    """Future Supabase Storage backend; the REST metadata repository is not one."""

    def materialize(self, key: str, destination: Path) -> Path:
        raise NotImplementedError("Supabase object storage is not configured")


class GitHubArtifactMediaStorage:
    """Future artifact downloader; CI should currently download/extract first."""

    def materialize(self, key: str, destination: Path) -> Path:
        raise NotImplementedError("download the GitHub artifact before rerendering")
