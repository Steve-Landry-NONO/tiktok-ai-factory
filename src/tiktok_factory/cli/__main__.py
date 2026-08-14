import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from tiktok_factory.pipeline.factory import FactoryPipeline
from tiktok_factory.pipeline.intelligent import IntelligentPipeline, MockIntelligentLLM
from tiktok_factory.pipeline.policies import BudgetPolicy
from tiktok_factory.providers.groq import GroqProvider
from tiktok_factory.providers.local import SyntheticVideoProvider
from tiktok_factory.providers.runway import RunwayProvider
from tiktok_factory.qa import review_technical
from tiktok_factory.storage.supabase import SupabaseRepository

LIVE_REQUIRED = ("GROQ_API_KEY", "SUPABASE_URL", "SUPABASE_SECRET_KEY")


def build_intelligent_pipeline(mode: str, video_provider: str = "synthetic") -> IntelligentPipeline:
    if video_provider not in ("synthetic", "runway"):
        raise RuntimeError(f"unsupported VIDEO_PROVIDER={video_provider}")

    if video_provider == "runway":
        if mode != "live":
            raise RuntimeError("Runway video generation is available only in live mode")
        if not os.getenv("RUNWAY_API_KEY"):
            raise RuntimeError("live Runway mode requires: RUNWAY_API_KEY")
        video = RunwayProvider(
            os.environ["RUNWAY_API_KEY"],
            model=os.getenv("RUNWAY_MODEL", "gen4.5"),
            ratio=os.getenv("RUNWAY_RATIO", "720:1280"),
            credits_per_second=float(os.getenv("RUNWAY_CREDITS_PER_SECOND", "12")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
        )
    else:
        video = SyntheticVideoProvider()

    media = FactoryPipeline(
        video,
        budget=BudgetPolicy(
            max_per_video=float(os.getenv("MAX_COST_PER_VIDEO", "10")),
            max_daily=float(os.getenv("MAX_DAILY_GENERATION_COST", "100")),
        ),
    )
    if mode == "mock":
        return IntelligentPipeline(MockIntelligentLLM(), media)

    missing = [name for name in LIVE_REQUIRED if not os.getenv(name)]
    if missing:
        raise RuntimeError("live mode requires: " + ", ".join(missing))
    provider_name = os.getenv("LLM_PROVIDER", "groq")
    if provider_name != "groq":
        raise RuntimeError(f"LLM_PROVIDER={provider_name} is not configured; supported now: groq")
    llm = GroqProvider(os.environ["GROQ_API_KEY"])
    repository = SupabaseRepository(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    return IntelligentPipeline(
        llm,
        media,
        repository,
        primary_model=os.getenv("GROQ_PRIMARY_MODEL", "openai/gpt-oss-120b"),
        judge_model=os.getenv("GROQ_JUDGE_MODEL", "openai/gpt-oss-20b"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="tiktok-factory")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--idea", required=True)
    generate.add_argument("--output", default="output/generated")
    demo = commands.add_parser("demo")
    demo.add_argument("--output", default="output/demo")
    validate = commands.add_parser("validate")
    validate.add_argument("path", type=Path)
    intelligent = commands.add_parser("intelligent-demo")
    intelligent.add_argument("--mode", choices=("mock", "live"), default="mock")
    intelligent.add_argument(
        "--video-provider",
        choices=("synthetic", "runway"),
        default=os.getenv("VIDEO_PROVIDER", "synthetic"),
    )
    intelligent.add_argument("--output", default="output/intelligent_demo")
    intelligent.add_argument(
        "--idea",
        default="A futuristic city where gravity reverses for exactly one minute every midnight",
    )
    intelligent.add_argument("--correlation-id")
    args = parser.parse_args()

    if args.command in ("generate", "demo"):
        idea = args.idea if args.command == "generate" else "A city where gravity changes every midnight"
        result = FactoryPipeline(SyntheticVideoProvider()).run(idea, Path(args.output))
        print(json.dumps({
            "status": result.status,
            "video": str(result.video.path),
            "metadata": str(result.metadata_path),
        }))
        return 0

    if args.command == "intelligent-demo":
        try:
            pipeline = build_intelligent_pipeline(args.mode, args.video_provider)
            result = pipeline.run(args.idea, Path(args.output), args.correlation_id)
        except RuntimeError as exc:
            print(f"error: {exc}")
            return 2
        print(json.dumps({
            "status": result.status,
            "idea_id": str(result.idea.id),
            "viral_score": result.viral_score.total,
            "llm_calls": len(pipeline.agent_runs),
            "video_provider": args.video_provider,
            "estimated_generation_cost_usd": round(sum(job.estimated_cost for job in result.jobs), 4),
            "video": str(result.video.path),
        }))
        return 0

    review = review_technical(uuid4(), args.path)
    print(review.model_dump_json(indent=2))
    return 0 if review.outcome == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
