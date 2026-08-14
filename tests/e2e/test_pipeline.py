import shutil
from pathlib import Path
import pytest
from tiktok_factory.domain.models import PipelineState,QAOutcome
from tiktok_factory.pipeline.factory import FactoryPipeline
from tiktok_factory.pipeline.renderer import probe
from tiktok_factory.providers.local import SyntheticVideoProvider

@pytest.mark.e2e
def test_pipeline_creates_valid_vertical_video():
 if not shutil.which('ffmpeg'): pytest.skip('ffmpeg unavailable')
 out=Path('output/e2e_test'); result=FactoryPipeline(SyntheticVideoProvider()).run('Why does an impossible city transform gravity every midnight in this amazing world?',out)
 assert result.status==PipelineState.READY_TO_PUBLISH
 assert result.reviews[0].outcome==QAOutcome.PASS
 data=probe(out/'final.mp4'); video=next(s for s in data['streams'] if s['codec_type']=='video')
 assert (video['width'],video['height'])==(1080,1920); assert video['codec_name']=='h264'; assert (out/'metadata.json').is_file()
