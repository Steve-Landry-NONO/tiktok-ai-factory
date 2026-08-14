import argparse
import json
from pathlib import Path

from tiktok_factory.pipeline.factory import FactoryPipeline
from tiktok_factory.providers.local import SyntheticVideoProvider
from tiktok_factory.qa import review_technical
from uuid import uuid4


def main() -> int:
    parser = argparse.ArgumentParser(prog="tiktok-factory")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate"); generate.add_argument("--idea", required=True); generate.add_argument("--output", default="output/generated")
    demo = commands.add_parser("demo"); demo.add_argument("--output", default="output/demo")
    validate = commands.add_parser("validate"); validate.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command in ("generate", "demo"):
        idea = args.idea if args.command == "generate" else "A city where gravity changes every midnight"
        result = FactoryPipeline(SyntheticVideoProvider()).run(idea, Path(args.output))
        print(json.dumps({"status": result.status, "video": str(result.video.path), "metadata": str(result.metadata_path)})); return 0
    review = review_technical(uuid4(), args.path)
    print(review.model_dump_json(indent=2)); return 0 if review.outcome == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
