from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from uuid import UUID

from tiktok_factory.domain.models import PerformanceMetric, StoryboardShot


class LLMProvider(ABC):
    @abstractmethod
    def structured(self, prompt: str, schema: type[Any]) -> Any: ...


class VideoGenerationProvider(ABC):
    name: str
    model: str
    estimated_cost: float

    @abstractmethod
    def generate(self, shot: StoryboardShot, destination: Path) -> Path: ...


class StorageProvider(ABC):
    @abstractmethod
    def put(self, source: Path, key: str) -> Path: ...


class AnalyticsProvider(ABC):
    @abstractmethod
    def metrics(self, publication_id: UUID) -> PerformanceMetric: ...


class PublishingProvider(ABC):
    @abstractmethod
    def publish(self, video: Path, metadata: dict[str, Any]) -> str: ...
