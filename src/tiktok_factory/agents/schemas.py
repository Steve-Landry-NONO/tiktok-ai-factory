from pydantic import Field
from tiktok_factory.domain.models import CreativeScores, StrictModel, ViralDimensions

class DirectorOutput(StrictModel): priority_topics: list[str]; rationale: str
class TrendScoutOutput(StrictModel): trends: list[str]; sources: list[str]
class CreativeProducerOutput(StrictModel): hook: str; narration: str; shots: list[str]
class ViralJudgeOutput(StrictModel): judge: str; dimensions: ViralDimensions; risk_flags: list[str] = Field(default_factory=list)
class QAAgentOutput(StrictModel): scores: CreativeScores; diagnostics: list[str] = Field(default_factory=list)
class GrowthAnalystOutput(StrictModel): winning_cohort: str; insights: list[str]; recommended_experiments: list[str]
