import json
from pathlib import Path
import httpx
import pytest
from tiktok_factory.domain.models import AgentRun, PipelineState, QAOutcome, QAReview, StoryboardShot
from tiktok_factory.pipeline.factory import FactoryPipeline
from tiktok_factory.pipeline.intelligent import IntelligentPipeline, MockIntelligentLLM
from tiktok_factory.providers.base import VideoGenerationProvider
from tiktok_factory.storage.supabase import (SupabaseAuthenticationError, SupabaseRepository)

class VideoFake(VideoGenerationProvider):
 name="fake"; model="fake"; estimated_cost=0.0
 def generate(self,shot:StoryboardShot,destination:Path)->Path:
  destination.parent.mkdir(parents=True,exist_ok=True); destination.write_bytes(b"video"); return destination
class RendererFake:
 def render(self,clips:list[Path],destination:Path,hook:str="")->Path:
  destination.write_bytes(b"render"); return destination
def technical(video,path): return QAReview(video_id=video.id,kind="technical",outcome=QAOutcome.PASS)

def make_repository(handler):
 client=httpx.Client(transport=httpx.MockTransport(handler),base_url="https://project.supabase.co")
 return SupabaseRepository("https://project.supabase.co","fake-server-secret",client=client,sleep=lambda delay:None)

def test_upsert_mapping_and_authorization_header():
 requests=[]
 def handler(request):
  requests.append(request); payload=json.loads(request.content)
  return httpx.Response(201,json=[payload])
 repo=make_repository(handler)
 run=AgentRun(agent="director",provider="groq",input={"seed":"safe"},output={"value":1})
 repo.save_agent_run(run,"judge-model")
 payload=json.loads(requests[0].content)
 assert requests[0].headers["apikey"]=="fake-server-secret"
 assert payload["id"]==str(run.id)
 assert payload["output"]["model"]=="judge-model"
 assert "authorization" not in json.dumps(payload).lower()

def test_complete_genealogy_persistence_and_readback(tmp_path):
 tables=[]; ideas={}
 def handler(request):
  table=request.url.path.rsplit("/",1)[-1]
  if request.method=="GET": return httpx.Response(200,json=[{"id":next(iter(ideas))}])
  payload=json.loads(request.content); tables.append(table)
  if table=="content_ideas": ideas[payload["id"]]=payload
  return httpx.Response(201,json=[payload])
 repo=make_repository(handler)
 media=FactoryPipeline(VideoFake(),renderer=RendererFake(),technical_reviewer=technical,
                       probe_fn=lambda path:{"format":{"duration":"1"}})
 result=IntelligentPipeline(MockIntelligentLLM(),media,repo).run("seed",tmp_path,"run-123")
 assert result.status==PipelineState.READY_TO_PUBLISH
 for table in ("content_ideas","scripts","storyboards","storyboard_shots","generation_jobs",
               "media_assets","videos","qa_reviews","agent_runs"):
  assert table in tables
 assert len([table for table in tables if table=="agent_runs"])==6
 assert ideas[str(result.idea.id)]["correlation_id"]=="run-123"

def test_authentication_error_is_not_retried():
 calls=[]
 def handler(request): calls.append(request); return httpx.Response(401,json={})
 repo=make_repository(handler)
 with pytest.raises(SupabaseAuthenticationError): repo.upsert("agent_runs",{"id":"x"})
 assert len(calls)==1
