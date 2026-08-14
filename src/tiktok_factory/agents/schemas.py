from pydantic import Field

from tiktok_factory.domain.models import CreativeScores, StrictModel, ViralDimensions


class DirectorOutput(StrictModel):
    enriched_concept: str
    target_audience: str
    creative_direction: str


class TrendScoutOutput(StrictModel):
    trends: list[str]
    sources: list[str]


class CreativeShotOutput(StrictModel):
    concept: str
    caption: str
    duration_seconds: float = Field(gt=0, le=10)


class CreativeProducerOutput(StrictModel):
    hook: str
    narration: str
    call_to_action: str
    shots: list[CreativeShotOutput] = Field(min_length=3, max_length=4)


class ViralJudgeOutput(StrictModel):
    judge: str
    dimensions: ViralDimensions
    risk_flags: list[str]


class QAAgentOutput(StrictModel):
    scores: CreativeScores
    diagnostics: list[str]


class GrowthAnalystOutput(StrictModel):
    winning_cohort: str
    insights: list[str]
    recommended_experiments: list[str]
