from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from uuid import UUID

from tiktok_factory.domain.models import CreativeScores, PerformanceMetric, StoryboardShot, Video


class LLMProvider(ABC):
    @abstractmethod
    def structured(self, prompt: str, schema: type[Any]) -> Any: ...


class VideoGenerationProvider(ABC):
    name: str
    model: str
    estimated_cost: float = 0.0

    def estimate_cost(self, shot: StoryboardShot) -> float:
        """Return the pre-call USD estimate for one generation."""
        del shot
        return self.estimated_cost

    @abstractmethod
    def generate(self, shot: StoryboardShot, destination: Path) -> Path: ...


class CreativeQAProvider(ABC):
    """Scores rendered creative output independently from technical QA."""

    @abstractmethod
    def evaluate(self, video: Video, attempt: int) -> CreativeScores: ...


class CostLedger(ABC):
    """Tracks already-consumed daily generation cost."""

    @abstractmethod
    def daily_spend(self) -> float: ...

    @abstractmethod
    def record(self, amount: float) -> None: ...


class StorageProvider(ABC):
    @abstractmethod
    def put(self, source: Path, key: str) -> Path: ...


class TextToSpeechProvider(ABC):
    """Turns narration into a local audio file."""

    @abstractmethod
    def synthesize(self, text: str, destination: Path) -> Path: ...


class AnalyticsProvider(ABC):
    @abstractmethod
    def metrics(self, publication_id: UUID) -> PerformanceMetric: ...


class PublishingProvider(ABC):
    @abstractmethod
    def publish(self, video: Path, metadata: dict[str, Any]) -> str: ...
