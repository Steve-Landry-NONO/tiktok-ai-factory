from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PipelineState(StrEnum):
    IDEA_CREATED = "IDEA_CREATED"
    IDEA_SCORED = "IDEA_SCORED"
    IDEA_REJECTED = "IDEA_REJECTED"
    SCRIPT_CREATED = "SCRIPT_CREATED"
    STORYBOARD_CREATED = "STORYBOARD_CREATED"
    GENERATION_PENDING = "GENERATION_PENDING"
    GENERATING = "GENERATING"
    GENERATION_FAILED = "GENERATION_FAILED"
    RENDER_PENDING = "RENDER_PENDING"
    RENDERING = "RENDERING"
    QA_PENDING = "QA_PENDING"
    QA_FAILED = "QA_FAILED"
    RETRY_REQUIRED = "RETRY_REQUIRED"
    READY_TO_PUBLISH = "READY_TO_PUBLISH"
    FAILED_PERMANENTLY = "FAILED_PERMANENTLY"


class ScoreDecision(StrEnum):
    REJECT = "REJECT"
    EXPERIMENT = "EXPERIMENT"
    CANDIDATE = "CANDIDATE"
    PRODUCE = "PRODUCE"
    PRIORITY = "PRIORITY"


class QAOutcome(StrEnum):
    PASS = "PASS"
    RETRYABLE = "RETRYABLE"
    FAIL = "FAIL"


class ContentIdea(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    concept: str = Field(min_length=3, max_length=1000)
    source: str = "manual"
    creator: str = "user"
    status: PipelineState = PipelineState.IDEA_CREATED
    created_at: datetime = Field(default_factory=utcnow)


class ViralDimensions(StrictModel):
    hook: float = Field(ge=0, le=20)
    curiosity_gap: float = Field(ge=0, le=15)
    visual_novelty: float = Field(ge=0, le=15)
    retention_potential: float = Field(ge=0, le=15)
    emotional_response: float = Field(ge=0, le=10)
    shareability: float = Field(ge=0, le=10)
    comment_potential: float = Field(ge=0, le=5)
    loop_potential: float = Field(ge=0, le=5)
    series_potential: float = Field(ge=0, le=5)

    @property
    def total(self) -> float:
        return sum(cast(float, value) for value in self.model_dump().values())


class ViralScore(StrictModel):
    dimensions: ViralDimensions
    total: float = Field(ge=0, le=100)
    decision: ScoreDecision
    confidence: float = Field(ge=0, le=1)
    judges: list[str] = Field(min_length=1)


class Script(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    idea_id: UUID
    hook: str
    narration: str
    call_to_action: str


class StoryboardShot(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    number: int = Field(ge=1)
    concept: str
    caption: str = ""
    duration_seconds: float = Field(gt=0, le=60)


class Storyboard(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    script_id: UUID
    shots: list[StoryboardShot] = Field(min_length=1)


class GenerationJob(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    shot_id: UUID
    provider: str
    model: str
    estimated_cost: float = Field(ge=0)
    actual_cost: float | None = Field(default=None, ge=0)
    attempt: int = Field(default=1, ge=1)
    status: PipelineState = PipelineState.GENERATION_PENDING


class MediaAsset(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    path: Path
    media_type: str = "video/mp4"
    duration_seconds: float = Field(gt=0)


class Video(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    storyboard_id: UUID
    path: Path
    profile: str = "tiktok_vertical_v1"
    status: PipelineState = PipelineState.QA_PENDING


class QAReview(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    video_id: UUID
    kind: str
    outcome: QAOutcome
    score: float | None = None
    checks: dict[str, bool] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)


class Publication(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    video_id: UUID
    provider: str = "tiktok"
    external_id: str | None = None
    published_at: datetime | None = None


class PerformanceMetric(StrictModel):
    publication_id: UUID
    views: int = Field(ge=0)
    likes: int = Field(ge=0)
    comments: int = Field(ge=0)
    shares: int = Field(ge=0)
    average_watch_time: float = Field(ge=0)
    completion_rate: float = Field(ge=0, le=1)
    followers_gained: int = Field(ge=0)


class Experiment(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    cohort: str
    dimensions: dict[str, str] = Field(default_factory=dict)


class AgentRun(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    agent: str
    provider: str
    input: dict[str, Any]
    output: dict[str, Any]
    created_at: datetime = Field(default_factory=utcnow)


class CreativeScores(StrictModel):
    hook: float = Field(ge=0, le=100)
    visual_clarity: float = Field(ge=0, le=100)
    pacing: float = Field(ge=0, le=100)
    coherence: float = Field(ge=0, le=100)
    artifact_risk: float = Field(ge=0, le=100)
    subtitle_readability: float = Field(ge=0, le=100)
    safe_zone_compliance: float = Field(ge=0, le=100)
    loop_quality: float = Field(ge=0, le=100)
    overall_score: float = Field(ge=0, le=100)


class PipelineResult(StrictModel):
    idea: ContentIdea
    viral_score: ViralScore
    script: Script
    storyboard: Storyboard
    jobs: list[GenerationJob]
    assets: list[MediaAsset]
    video: Video
    reviews: list[QAReview]
    status: PipelineState
    attempts: int
    diagnostics: list[str] = Field(default_factory=list)
    state_history: list[PipelineState] = Field(default_factory=list)
    metadata_path: Path
