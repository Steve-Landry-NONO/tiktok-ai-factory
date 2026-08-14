from pathlib import Path
import pytest
from tiktok_factory.cli.__main__ import build_intelligent_pipeline
from tiktok_factory.domain.models import PipelineState, QAOutcome, QAReview, StoryboardShot
from tiktok_factory.pipeline.factory import FactoryPipeline
from tiktok_factory.pipeline.intelligent import IntelligentPipeline, MockIntelligentLLM
from tiktok_factory.providers.base import VideoGenerationProvider

class VideoFake(VideoGenerationProvider):
 name="fake"; model="fake"; estimated_cost=0.0
 def generate(self,shot:StoryboardShot,destination:Path)->Path:
  destination.parent.mkdir(parents=True,exist_ok=True); destination.write_bytes(b"video"); return destination
class RendererFake:
 def render(self,clips:list[Path],destination:Path,hook:str="")->Path:
  destination.write_bytes(b"render"); return destination
def technical(video,path): return QAReview(video_id=video.id,kind="technical",outcome=QAOutcome.PASS)

def test_mock_intelligent_pipeline_uses_six_agents_without_secrets(tmp_path,monkeypatch):
 for name in ("GROQ_API_KEY","SUPABASE_URL","SUPABASE_SECRET_KEY"): monkeypatch.delenv(name,raising=False)
 llm=MockIntelligentLLM()
 media=FactoryPipeline(VideoFake(),renderer=RendererFake(),technical_reviewer=technical,
                       probe_fn=lambda path:{"format":{"duration":"1"}})
 result=IntelligentPipeline(llm,media).run("seed",tmp_path)
 assert result.status==PipelineState.READY_TO_PUBLISH
 assert llm.call_count==6 and len(result.storyboard.shots)==3
 assert [model for _,model in llm.calls[:2]]==["openai/gpt-oss-120b"]*2
 assert [model for _,model in llm.calls[2:]]==["openai/gpt-oss-20b"]*4


def test_correlation_id_makes_genealogy_ids_idempotent(tmp_path):
 def execute(folder):
  media=FactoryPipeline(VideoFake(),renderer=RendererFake(),technical_reviewer=technical,
                        probe_fn=lambda path:{"format":{"duration":"1"}})
  return IntelligentPipeline(MockIntelligentLLM(),media).run("seed",folder,"stable-run")
 first=execute(tmp_path/"one")
 second=execute(tmp_path/"two")
 assert first.idea.id==second.idea.id
 assert first.script.id==second.script.id
 assert first.storyboard.id==second.storyboard.id
 assert [shot.id for shot in first.storyboard.shots]==[shot.id for shot in second.storyboard.shots]
 assert [job.id for job in first.jobs]==[job.id for job in second.jobs]
 assert first.video.id==second.video.id

def test_mock_mode_builds_without_secrets(monkeypatch):
 for name in ("GROQ_API_KEY","SUPABASE_URL","SUPABASE_SECRET_KEY"): monkeypatch.delenv(name,raising=False)
 assert build_intelligent_pipeline("mock").llm.name=="mock"

def test_live_mode_refuses_missing_credentials(monkeypatch):
 for name in ("GROQ_API_KEY","SUPABASE_URL","SUPABASE_SECRET_KEY"): monkeypatch.delenv(name,raising=False)
 with pytest.raises(RuntimeError,match="live mode requires"):
  build_intelligent_pipeline("live")
