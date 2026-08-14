import json
import httpx
import pytest
from tiktok_factory.agents.schemas import DirectorOutput
from tiktok_factory.providers.groq import (GroqProvider, LLMAuthenticationError,
    LLMProviderError, LLMResponseError)

VALID = {"enriched_concept":"A richer city concept","target_audience":"curious viewers",
         "creative_direction":"cinematic"}

def response(data, status=200):
    return httpx.Response(status, json=data)

def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.groq.test")

def test_structured_output_and_strict_schema_request():
    seen={}
    def handler(request):
        seen.update(json.loads(request.content)); assert request.headers["authorization"].startswith("Bearer ")
        return response({"choices":[{"message":{"content":json.dumps(VALID)}}]})
    result=GroqProvider("not-a-real-secret",client=client(handler)).structured("director","seed",DirectorOutput,"model")
    assert result.enriched_concept==VALID["enriched_concept"]
    assert seen["response_format"]["json_schema"]["strict"] is True

def test_invalid_schema_is_sanitized():
    provider=GroqProvider("fake",client=client(lambda request: response({"choices":[{"message":{"content":"{}"}}]})))
    with pytest.raises(LLMResponseError,match="invalid structured response"):
        provider.structured("director","seed",DirectorOutput,"model")

def test_429_retries_then_succeeds():
    calls=[]
    def handler(request):
        calls.append(request)
        if len(calls)<3: return response({},429)
        return response({"choices":[{"message":{"content":json.dumps(VALID)}}]})
    provider=GroqProvider("fake",client=client(handler),sleep=lambda delay: None)
    assert provider.structured("director","seed",DirectorOutput,"model").target_audience
    assert len(calls)==3

def test_401_never_retries():
    calls=[]
    def handler(request): calls.append(request); return response({},401)
    provider=GroqProvider("fake",client=client(handler),sleep=lambda delay: None)
    with pytest.raises(LLMAuthenticationError):
        provider.structured("director","seed",DirectorOutput,"model")
    assert len(calls)==1


def test_timeout_retries_are_bounded():
    calls=[]
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout",request=request)
    provider=GroqProvider("fake",client=client(handler),max_retries=2,sleep=lambda delay:None)
    with pytest.raises(LLMProviderError,match="network request failed after retries"):
        provider.structured("director","seed",DirectorOutput,"model")
    assert len(calls)==3
