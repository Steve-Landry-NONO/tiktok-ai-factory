import pytest
from pydantic import ValidationError
from tiktok_factory.domain.models import ContentIdea, PipelineState, QAOutcome
from tiktok_factory.pipeline.policies import BudgetPolicy, BudgetExceededError, RetryPolicy, transition, InvalidTransitionError
from tiktok_factory.qa import creative_outcome

def test_strict_schema():
 with pytest.raises(ValidationError): ContentIdea(concept='valid', unknown=True)
def test_states():
 assert transition(PipelineState.IDEA_CREATED,PipelineState.IDEA_SCORED)==PipelineState.IDEA_SCORED
 with pytest.raises(InvalidTransitionError): transition(PipelineState.IDEA_CREATED,PipelineState.RENDERING)
def test_retry_is_bounded():
 p=RetryPolicy(2); assert p.record_failure('a')==PipelineState.RETRY_REQUIRED; assert p.record_failure('b')==PipelineState.RETRY_REQUIRED; assert p.record_failure('c')==PipelineState.FAILED_PERMANENTLY
def test_budget():
 BudgetPolicy().authorize(1,2,3)
 with pytest.raises(BudgetExceededError): BudgetPolicy(2,100).authorize(1,2,0)
def test_creative_thresholds():
 assert creative_outcome(85)==QAOutcome.PASS; assert creative_outcome(75)==QAOutcome.RETRYABLE; assert creative_outcome(74.9)==QAOutcome.FAIL
