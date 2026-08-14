from dataclasses import dataclass, field

from tiktok_factory.domain.models import PipelineState


class BudgetExceededError(RuntimeError): pass
class InvalidTransitionError(RuntimeError): pass


@dataclass(frozen=True)
class BudgetPolicy:
    max_per_video: float = 10.0
    max_daily: float = 100.0
    def authorize(self, estimated: float, video_spend: float, daily_spend: float) -> None:
        if estimated + video_spend > self.max_per_video or estimated + daily_spend > self.max_daily:
            raise BudgetExceededError("generation blocked before execution: budget exceeded")


@dataclass
class RetryPolicy:
    max_retries: int = 3
    attempts: list[str] = field(default_factory=list)
    def record_failure(self, diagnostic: str) -> PipelineState:
        self.attempts.append(diagnostic)
        return (PipelineState.RETRY_REQUIRED if len(self.attempts) <= self.max_retries
                else PipelineState.FAILED_PERMANENTLY)


TRANSITIONS = {
 PipelineState.IDEA_CREATED: {PipelineState.IDEA_SCORED, PipelineState.IDEA_REJECTED},
 PipelineState.IDEA_SCORED: {PipelineState.SCRIPT_CREATED},
 PipelineState.SCRIPT_CREATED: {PipelineState.STORYBOARD_CREATED},
 PipelineState.STORYBOARD_CREATED: {PipelineState.GENERATION_PENDING},
 PipelineState.GENERATION_PENDING: {PipelineState.GENERATING},
 PipelineState.GENERATING: {PipelineState.GENERATION_FAILED, PipelineState.RENDER_PENDING},
 PipelineState.GENERATION_FAILED: {PipelineState.RETRY_REQUIRED, PipelineState.FAILED_PERMANENTLY},
 PipelineState.RENDER_PENDING: {PipelineState.RENDERING},
 PipelineState.RENDERING: {PipelineState.QA_PENDING, PipelineState.RETRY_REQUIRED},
 PipelineState.QA_PENDING: {PipelineState.QA_FAILED, PipelineState.READY_TO_PUBLISH},
 PipelineState.QA_FAILED: {PipelineState.RETRY_REQUIRED, PipelineState.FAILED_PERMANENTLY},
 PipelineState.RETRY_REQUIRED: {PipelineState.GENERATION_PENDING, PipelineState.RENDER_PENDING, PipelineState.FAILED_PERMANENTLY},
}

def transition(current: PipelineState, target: PipelineState) -> PipelineState:
    if target not in TRANSITIONS.get(current, set()): raise InvalidTransitionError(f"{current} -> {target}")
    return target
