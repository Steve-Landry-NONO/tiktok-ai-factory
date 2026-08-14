from pathlib import Path

import pytest

from tiktok_factory.domain.models import PipelineState, QAOutcome, QAReview, StoryboardShot
from tiktok_factory.pipeline.factory import FactoryPipeline
from tiktok_factory.pipeline.policies import BudgetExceededError, BudgetPolicy, RetryPolicy
from tiktok_factory.providers.base import VideoGenerationProvider
from tiktok_factory.providers.local import InMemoryCostLedger, MockCreativeQAProvider


class FakeVideoProvider(VideoGenerationProvider):
    name = "fake"
    model = "fake-v1"

    def __init__(self, cost: float = 0.0):
        self.estimated_cost = cost
        self.calls = 0

    def generate(self, shot: StoryboardShot, destination: Path) -> Path:
        del shot
        self.calls += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"fake-video")
        return destination


class FakeRenderer:
    def render(self, clips: list[Path], destination: Path, hook: str = "") -> Path:
        assert clips and hook
        destination.write_bytes(b"rendered-video")
        return destination


def passing_technical(video, path):
    assert path.is_file()
    return QAReview(video_id=video.id, kind="technical", outcome=QAOutcome.PASS)


def pipeline(provider, scores, max_retries=3, ledger=None, budget=None):
    return FactoryPipeline(
        provider,
        renderer=FakeRenderer(),
        creative_qa=MockCreativeQAProvider(scores),
        retry=RetryPolicy(max_retries),
        ledger=ledger,
        budget=budget,
        technical_reviewer=passing_technical,
        probe_fn=lambda path: {"format": {"duration": "1.0"}},
    )


IDEA = "Why does an impossible city transform gravity every midnight in this amazing world?"


def test_success_on_first_attempt(tmp_path):
    provider = FakeVideoProvider()
    result = pipeline(provider, [90]).run(IDEA, tmp_path)
    assert result.status == PipelineState.READY_TO_PUBLISH
    assert result.attempts == 1
    assert {job.attempt for job in result.jobs} == {1}
    assert result.diagnostics == []


def test_failure_then_success_regenerates(tmp_path):
    provider = FakeVideoProvider()
    result = pipeline(provider, [80, 90]).run(IDEA, tmp_path)
    assert result.status == PipelineState.READY_TO_PUBLISH
    assert result.attempts == 2
    assert [job.attempt for job in result.jobs] == [1, 1, 1, 2, 2, 2]
    assert len(result.diagnostics) == 1
    assert PipelineState.RETRY_REQUIRED in result.state_history
    assert provider.calls == 6


def test_multiple_failures_then_success(tmp_path):
    result = pipeline(FakeVideoProvider(), [20, 80, 90]).run(IDEA, tmp_path)
    assert result.status == PipelineState.READY_TO_PUBLISH
    assert result.attempts == 3
    assert len(result.diagnostics) == 2


def test_exceeding_retries_is_permanent(tmp_path):
    result = pipeline(FakeVideoProvider(), [20], max_retries=2).run(IDEA, tmp_path)
    assert result.status == PipelineState.FAILED_PERMANENTLY
    assert result.attempts == 3
    assert len(result.diagnostics) == 3
    assert result.state_history[-1] == PipelineState.FAILED_PERMANENTLY


def test_daily_budget_blocks_before_provider_call(tmp_path):
    provider = FakeVideoProvider(cost=1.0)
    factory = pipeline(provider, [90], ledger=InMemoryCostLedger(10), budget=BudgetPolicy(10, 10))
    with pytest.raises(BudgetExceededError):
        factory.run(IDEA, tmp_path)
    assert provider.calls == 0


def test_per_video_budget_preflights_whole_attempt_before_any_generation(tmp_path):
    provider = FakeVideoProvider(cost=1.0)
    factory = pipeline(provider, [90], budget=BudgetPolicy(2, 100))
    with pytest.raises(BudgetExceededError):
        factory.run(IDEA, tmp_path)
    assert provider.calls == 0
