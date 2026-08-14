from uuid import uuid4
from tiktok_factory.agents import DirectorOutput
from tiktok_factory.domain.models import StoryboardShot
from tiktok_factory.pipeline.renderer import probe
from tiktok_factory.providers.local import MockLLMProvider, SyntheticVideoProvider, LocalStorageProvider, MockAnalyticsProvider

def test_mock_llm_structured(): assert MockLLMProvider({'priority_topics':['x'],'rationale':'y'}).structured('p',DirectorOutput).priority_topics==['x']
def test_local_storage(tmp_path):
 p=tmp_path/'a'; p.write_text('x'); assert LocalStorageProvider(tmp_path/'store').put(p,'nested/a').read_text()=='x'
def test_metrics(): assert MockAnalyticsProvider().metrics(uuid4()).views==1000
def test_synthetic_ffmpeg(tmp_path):
 p=SyntheticVideoProvider(width=320,height=568).generate(StoryboardShot(number=1,concept='test',duration_seconds=.2),tmp_path/'clip.mp4')
 assert probe(p)['streams'][0]['codec_name']=='h264'
