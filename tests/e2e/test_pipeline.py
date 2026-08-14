import json
from pathlib import Path

import pytest

from tiktok_factory.domain.models import PipelineState, QAOutcome
from tiktok_factory.pipeline.factory import FactoryPipeline
from tiktok_factory.pipeline.renderer import probe
from tiktok_factory.providers.local import MockCreativeQAProvider, SyntheticVideoProvider


@pytest.mark.e2e
def test_pipeline_creates_valid_vertical_video():
    output = Path("output/e2e_test")
    result = FactoryPipeline(
        SyntheticVideoProvider(), creative_qa=MockCreativeQAProvider([90])
    ).run(
        "Why does an impossible city transform gravity every midnight in this amazing world?",
        output,
    )
    final = output / "final.mp4"
    metadata_path = output / "metadata.json"
    assert result.status == PipelineState.READY_TO_PUBLISH
    assert result.reviews[-2].kind == "technical"
    assert result.reviews[-2].outcome == QAOutcome.PASS
    assert result.reviews[-1].kind == "creative"
    assert result.reviews[-1].outcome == QAOutcome.PASS
    assert final.is_file() and final.stat().st_size > 0
    data = probe(final)
    video = next(stream for stream in data["streams"] if stream["codec_type"] == "video")
    numerator, denominator = video["avg_frame_rate"].split("/")
    assert video["codec_name"] == "h264"
    assert (video["width"], video["height"]) == (1080, 1920)
    assert abs(float(numerator) / float(denominator) - 30) < 0.1
    assert float(data["format"]["duration"]) > 0
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["status"] == PipelineState.READY_TO_PUBLISH
    assert metadata["attempts"] == 1
