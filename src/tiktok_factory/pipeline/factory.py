import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from tiktok_factory.domain.models import (
    ContentIdea,
    GenerationJob,
    MediaAsset,
    PipelineResult,
    PipelineState,
    QAOutcome,
    QAReview,
    Script,
    Storyboard,
    StoryboardShot,
    Video,
)
from tiktok_factory.pipeline.policies import BudgetPolicy, RetryPolicy, transition
from tiktok_factory.pipeline.renderer import FFmpegRenderer, probe
from tiktok_factory.providers.base import CostLedger, CreativeQAProvider, VideoGenerationProvider
from tiktok_factory.providers.local import InMemoryCostLedger, MockCreativeQAProvider
from tiktok_factory.qa import review_creative, review_technical
from tiktok_factory.scoring import aggregate_scores, deterministic_dimensions


class PipelineRejectedError(RuntimeError):
    pass


TechnicalReviewer = Callable[[Video, Path], QAReview]
ProbeFunction = Callable[[Path], dict[str, Any]]


class Renderer(Protocol):
    def render(self, clips: list[Path], destination: Path, hook: str = "") -> Path: ...


def default_technical_reviewer(video: Video, path: Path) -> QAReview:
    return review_technical(video.id, path)


class FactoryPipeline:
    """Synchronous application service with bounded, observable QA retries."""

    def __init__(
        self,
        provider: VideoGenerationProvider,
        renderer: Renderer | None = None,
        budget: BudgetPolicy | None = None,
        retry: RetryPolicy | None = None,
        creative_qa: CreativeQAProvider | None = None,
        ledger: CostLedger | None = None,
        technical_reviewer: TechnicalReviewer = default_technical_reviewer,
        probe_fn: ProbeFunction = probe,
    ):
        self.provider = provider
        self.renderer = renderer or FFmpegRenderer()
        self.budget = budget or BudgetPolicy()
        self.retry = retry or RetryPolicy()
        self.creative_qa = creative_qa or MockCreativeQAProvider()
        self.ledger = ledger or InMemoryCostLedger()
        self.technical_reviewer = technical_reviewer
        self.probe_fn = probe_fn

    def run(self, concept: str, output_dir: Path, force: bool = False) -> PipelineResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        idea = ContentIdea(concept=concept)
        state = idea.status
        history = [state]

        def advance(target: PipelineState) -> None:
            nonlocal state
            state = transition(state, target)
            history.append(state)

        score_dimensions = deterministic_dimensions(concept)
        score = aggregate_scores([
            ("viral_judge_a", score_dimensions),
            ("viral_judge_b", score_dimensions),
            ("novelty_judge", score_dimensions),
            ("risk_judge", score_dimensions),
        ])
        advance(PipelineState.IDEA_SCORED)
        idea.status = state
        if score.total < 55 and not force:
            advance(PipelineState.IDEA_REJECTED)
            idea.status = state
            raise PipelineRejectedError(f"idea rejected with score {score.total}")

        script = Script(
            idea_id=idea.id,
            hook=concept,
            narration=f"Imagine this: {concept}. What happens next?",
            call_to_action="Would you enter this world? Comment below.",
        )
        advance(PipelineState.SCRIPT_CREATED)
        shots = [
            StoryboardShot(number=i, concept=text, caption=text, duration_seconds=1.0)
            for i, text in enumerate((
                f"The hook — {concept}",
                "The unexpected transformation",
                "A seamless return to the opening",
            ), 1)
        ]
        board = Storyboard(script_id=script.id, shots=shots)
        advance(PipelineState.STORYBOARD_CREATED)
        advance(PipelineState.GENERATION_PENDING)

        jobs: list[GenerationJob] = []
        reviews: list[QAReview] = []
        diagnostics: list[str] = []
        video_spend = 0.0
        attempt = 0
        final_assets: list[MediaAsset] = []
        video: Video | None = None

        while True:
            attempt += 1
            advance(PipelineState.GENERATING)
            attempt_assets: list[MediaAsset] = []
            for shot in shots:
                estimate = self.provider.estimated_cost
                self.budget.authorize(estimate, video_spend, self.ledger.daily_spend())
                job = GenerationJob(
                    shot_id=shot.id,
                    provider=self.provider.name,
                    model=self.provider.model,
                    estimated_cost=estimate,
                    attempt=attempt,
                    status=PipelineState.GENERATING,
                )
                path = self.provider.generate(
                    shot, output_dir / "clips" / f"attempt_{attempt}" / f"shot_{shot.number}.mp4"
                )
                job.actual_cost = estimate
                job.status = PipelineState.RENDER_PENDING
                jobs.append(job)
                video_spend += estimate
                self.ledger.record(estimate)
                info = self.probe_fn(path)
                duration = float(info["format"]["duration"])
                attempt_assets.append(MediaAsset(job_id=job.id, path=path, duration_seconds=duration))

            advance(PipelineState.RENDER_PENDING)
            advance(PipelineState.RENDERING)
            final_path = self.renderer.render(
                [asset.path for asset in attempt_assets], output_dir / "final.mp4", script.hook
            )
            video = Video(storyboard_id=board.id, path=final_path)
            advance(PipelineState.QA_PENDING)
            technical = self.technical_reviewer(video, final_path)
            creative = review_creative(video.id, self.creative_qa.evaluate(video, attempt))
            reviews.extend((technical, creative))
            final_assets = attempt_assets

            if technical.outcome == QAOutcome.PASS and creative.outcome == QAOutcome.PASS:
                advance(PipelineState.READY_TO_PUBLISH)
                break

            advance(PipelineState.QA_FAILED)
            diagnostic = (
                f"attempt {attempt}: technical={technical.outcome.value}, "
                f"creative={creative.outcome.value}; "
                + "; ".join(technical.diagnostics + creative.diagnostics)
            ).rstrip("; ")
            diagnostics.append(diagnostic)
            retry_state = self.retry.record_failure(diagnostic)
            advance(retry_state)
            if retry_state == PipelineState.FAILED_PERMANENTLY:
                break
            advance(PipelineState.GENERATION_PENDING)

        assert video is not None
        video.status = state
        metadata_path = output_dir / "metadata.json"
        result = PipelineResult(
            idea=idea,
            viral_score=score,
            script=script,
            storyboard=board,
            jobs=jobs,
            assets=final_assets,
            video=video,
            reviews=reviews,
            status=state,
            attempts=attempt,
            diagnostics=diagnostics,
            state_history=history,
            metadata_path=metadata_path,
        )
        metadata_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2), encoding="utf-8")
        return result
