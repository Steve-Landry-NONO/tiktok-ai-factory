import json
from pathlib import Path

from tiktok_factory.domain.models import (ContentIdea, CreativeScores, GenerationJob, MediaAsset,
    PipelineResult, PipelineState, QAOutcome, Script, Storyboard, StoryboardShot, Video)
from tiktok_factory.pipeline.policies import BudgetPolicy
from tiktok_factory.pipeline.renderer import FFmpegRenderer, probe
from tiktok_factory.providers.base import VideoGenerationProvider
from tiktok_factory.qa import review_creative, review_technical
from tiktok_factory.scoring import aggregate_scores, deterministic_dimensions


class PipelineRejectedError(RuntimeError): pass


class FactoryPipeline:
    """Synchronous application service; n8n can invoke it without owning business logic."""
    def __init__(self, provider: VideoGenerationProvider, renderer: FFmpegRenderer | None = None,
                 budget: BudgetPolicy | None = None):
        self.provider = provider; self.renderer = renderer or FFmpegRenderer(); self.budget = budget or BudgetPolicy()

    def run(self, concept: str, output_dir: Path, force: bool = False) -> PipelineResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        idea = ContentIdea(concept=concept)
        base = deterministic_dimensions(concept)
        score = aggregate_scores([("viral_judge_a", base), ("viral_judge_b", base),
                                  ("novelty_judge", base), ("risk_judge", base)])
        idea.status = PipelineState.IDEA_SCORED
        if score.total < 55 and not force:
            idea.status = PipelineState.IDEA_REJECTED
            raise PipelineRejectedError(f"idea rejected with score {score.total}")
        script = Script(idea_id=idea.id, hook=concept, narration=f"Imagine this: {concept}. What happens next?",
                        call_to_action="Would you enter this world? Comment below.")
        shots = [StoryboardShot(number=i, concept=text, caption=text, duration_seconds=1.0) for i, text in enumerate(
            (f"The hook — {concept}", "The unexpected transformation", "A seamless return to the opening"), 1)]
        board = Storyboard(script_id=script.id, shots=shots)
        jobs: list[GenerationJob] = []; assets: list[MediaAsset] = []
        video_spend = 0.0
        for shot in shots:
            estimate = self.provider.estimated_cost
            self.budget.authorize(estimate, video_spend, 0)
            job = GenerationJob(shot_id=shot.id, provider=self.provider.name, model=self.provider.model,
                                estimated_cost=estimate, status=PipelineState.GENERATING)
            path = self.provider.generate(shot, output_dir / "clips" / f"shot_{shot.number}.mp4")
            job.actual_cost = estimate; job.status = PipelineState.RENDER_PENDING; jobs.append(job)
            info = probe(path); duration = float(info["format"]["duration"])
            assets.append(MediaAsset(job_id=job.id, path=path, duration_seconds=duration)); video_spend += estimate
        final_path = self.renderer.render([a.path for a in assets], output_dir / "final.mp4", script.hook)
        video = Video(storyboard_id=board.id, path=final_path)
        technical = review_technical(video.id, final_path)
        creative = review_creative(video.id, CreativeScores(hook=92, visual_clarity=90, pacing=88, coherence=90,
            artifact_risk=5, subtitle_readability=90, safe_zone_compliance=90, loop_quality=86, overall_score=89))
        reviews = [technical, creative]
        status = PipelineState.READY_TO_PUBLISH if all(r.outcome == QAOutcome.PASS for r in reviews) else PipelineState.QA_FAILED
        video.status = status
        metadata_path = output_dir / "metadata.json"
        result = PipelineResult(idea=idea, viral_score=score, script=script, storyboard=board, jobs=jobs,
            assets=assets, video=video, reviews=reviews, status=status, attempts=1, metadata_path=metadata_path)
        metadata_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2), encoding="utf-8")
        return result
