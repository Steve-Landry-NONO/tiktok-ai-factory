"""Agent-driven V2 orchestration layered on the tested media pipeline."""
import json
from pathlib import Path
from typing import Any, Protocol, TypeVar
from uuid import NAMESPACE_URL, uuid5
from pydantic import BaseModel
from tiktok_factory.agents.schemas import DirectorOutput, CreativeProducerOutput, ViralJudgeOutput
from tiktok_factory.domain.models import AgentRun, ContentIdea, PipelineResult, StoryboardShot
from tiktok_factory.pipeline.factory import FactoryPipeline, PipelineRejectedError
from tiktok_factory.scoring import aggregate_scores

T = TypeVar("T", bound=BaseModel)
JUDGES = ("viral_judge_a", "viral_judge_b", "novelty_judge", "risk_judge")

class StructuredProvider(Protocol):
    name: str
    def structured(self, agent: str, prompt: str, schema: type[T], model: str) -> T: ...

class PipelineRepository(Protocol):
    def save_agent_run(self, run: AgentRun, model: str) -> None: ...
    def persist_pipeline(self, result: PipelineResult, correlation_id: str) -> None: ...
    def idea_exists(self, idea_id: str) -> bool: ...

class IntelligentPipeline:
    def __init__(self, llm: StructuredProvider, media_pipeline: FactoryPipeline,
                 repository: PipelineRepository | None = None,
                 primary_model: str = "openai/gpt-oss-120b",
                 judge_model: str = "openai/gpt-oss-20b"):
        self.llm, self.media_pipeline, self.repository = llm, media_pipeline, repository
        self.primary_model, self.judge_model = primary_model, judge_model
        self.agent_runs: list[AgentRun] = []

    def run(self, seed: str, output_dir: Path, correlation_id: str | None = None) -> PipelineResult:
        correlation_id = correlation_id or str(uuid5(NAMESPACE_URL, seed))
        director = self._call("director", self._director_prompt(seed), DirectorOutput, self.primary_model)
        creative = self._call("creative_producer", self._creative_prompt(director),
                              CreativeProducerOutput, self.primary_model)
        judge_prompt = self._judge_prompt(director, creative)
        evaluations = []
        for judge in JUDGES:
            output = self._call(judge, judge_prompt, ViralJudgeOutput, self.judge_model)
            evaluations.append((judge, output.dimensions))
        score = aggregate_scores(evaluations)
        if score.total < 55:
            raise PipelineRejectedError(f"independent judges rejected idea with score {score.total}")

        idea_id = uuid5(NAMESPACE_URL, f"{correlation_id}:idea")
        script_id = uuid5(NAMESPACE_URL, f"{correlation_id}:script")
        storyboard_id = uuid5(NAMESPACE_URL, f"{correlation_id}:storyboard")
        idea = ContentIdea(id=idea_id, concept=director.enriched_concept, source="intelligent_pipeline", creator="director")
        shots = [StoryboardShot(id=uuid5(NAMESPACE_URL, f"{correlation_id}:shot:{number}"),
            number=number, concept=shot.concept, caption=shot.caption,
            duration_seconds=shot.duration_seconds) for number, shot in enumerate(creative.shots, 1)]
        result = self.media_pipeline.run(director.enriched_concept, output_dir, idea=idea,
            viral_score=score, script_content=(creative.hook, creative.narration, creative.call_to_action),
            prepared_shots=shots, script_id=script_id, storyboard_id=storyboard_id,
            idempotency_key=correlation_id)
        if self.repository:
            self.repository.persist_pipeline(result, correlation_id)
            if not self.repository.idea_exists(str(result.idea.id)):
                raise RuntimeError("Supabase read-after-write verification failed")
        return result

    def _call(self, agent: str, prompt: str, schema: type[T], model: str) -> T:
        output = self.llm.structured(agent, prompt, schema, model)
        run = AgentRun(agent=agent, provider=self.llm.name, input={"prompt": prompt},
                       output=output.model_dump(mode="json"))
        self.agent_runs.append(run)
        if self.repository: self.repository.save_agent_run(run, model)
        return output

    @staticmethod
    def _director_prompt(seed: str) -> str:
        return f"Enrich this TikTok seed into one visual, safe concept: {seed}"

    @staticmethod
    def _creative_prompt(director: DirectorOutput) -> str:
        return "Create a short vertical-video script and 3-5 shots from: " + director.model_dump_json()

    @staticmethod
    def _judge_prompt(director: DirectorOutput, creative: CreativeProducerOutput) -> str:
        return "Independently score this proposal. Never assume virality. " + json.dumps({
            "director": director.model_dump(mode="json"), "creative": creative.model_dump(mode="json")})


class MockIntelligentLLM:
    """Offline deterministic six-agent provider."""
    name = "mock"
    def __init__(self) -> None:
        self.call_count = 0
        self.calls: list[tuple[str, str]] = []
    def structured(self, agent: str, prompt: str, schema: type[T], model: str) -> T:
        del prompt
        self.call_count += 1
        self.calls.append((agent, model))
        if schema is DirectorOutput:
            data: dict[str, Any] = {"enriched_concept": "A futuristic city where gravity reverses for one minute every midnight",
                    "target_audience": "science-fiction curious viewers",
                    "creative_direction": "cinematic neon transformations with a seamless loop"}
        elif schema is CreativeProducerOutput:
            data = {"hook": "At midnight, this entire city falls upward.",
                    "narration": "For exactly sixty seconds, gravity reverses—and everyone prepares for the skyfall.",
                    "call_to_action": "What would you anchor first?",
                    "shots": [{"concept": "Neon skyline moments before midnight", "caption": "11:59:59", "duration_seconds": 1},
                              {"concept": "People and objects drift upward", "caption": "Gravity reversed", "duration_seconds": 1},
                              {"concept": "Everything lands as the clock resets", "caption": "Until tomorrow", "duration_seconds": 1}]}
        else:
            data = {"judge": agent, "dimensions": {"hook": 18, "curiosity_gap": 13,
                "visual_novelty": 14, "retention_potential": 13, "emotional_response": 8,
                "shareability": 8, "comment_potential": 4, "loop_potential": 5,
                "series_potential": 4}, "risk_flags": []}
        return schema.model_validate(data)
