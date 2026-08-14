import json
from io import BytesIO
import wave

import httpx
import pytest

from tiktok_factory.providers.groq_tts import (
    ORPHEUS_ENGLISH_MODEL,
    ORPHEUS_MAX_INPUT_CHARS,
    GroqTextToSpeech,
    normalize_tts_text,
    split_tts_text,
)


def _wav_bytes(frames: int = 80) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16_000)
        writer.writeframes(b"\x00\x00" * frames)
    return buffer.getvalue()


def test_groq_tts_writes_audio_without_exposing_secret(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=b"RIFFfake")

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.groq.com/openai/v1"
    )
    output = GroqTextToSpeech("secret", client=client).synthesize(
        "Narration", tmp_path / "voice.wav"
    )
    assert output.read_bytes() == b"RIFFfake"
    assert requests[0].url.path == "/openai/v1/audio/speech"
    assert b"secret" not in requests[0].content
    payload = json.loads(requests[0].content)
    assert payload["model"] == ORPHEUS_ENGLISH_MODEL
    assert payload["voice"] == "troy"
    assert payload["response_format"] == "wav"


def test_groq_tts_retries_transient_errors(tmp_path):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503 if calls == 1 else 200, content=b"audio")

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.groq.com/openai/v1"
    )
    GroqTextToSpeech("secret", client=client, sleep=lambda _: None).synthesize(
        "Text", tmp_path / "a.wav"
    )
    assert calls == 2


def test_normalize_tts_text_replaces_typographic_punctuation():
    value = normalize_tts_text("Midnight strikes—neon‑lit city… it’s weightless.")
    assert value == "Midnight strikes-neon-lit city... it's weightless."


def test_split_tts_text_keeps_every_chunk_within_orpheus_limit():
    text = (
        "Midnight strikes and the city begins to float. "
        "Cars lift from the road while people reach for anything they can hold. "
        "For one impossible minute the skyline turns into a weightless dream. "
        "Then gravity snaps back and the whole city carries on as if nothing happened."
    )
    chunks = split_tts_text(text)
    assert len(chunks) >= 2
    assert all(0 < len(chunk) <= ORPHEUS_MAX_INPUT_CHARS for chunk in chunks)
    assert " ".join(chunks) == " ".join(text.split())


def test_groq_tts_chunks_long_narration_and_merges_wav(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=_wav_bytes(80))

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.groq.com/openai/v1"
    )
    text = " ".join(["A cinematic gravity reversal unfolds across the neon city."] * 7)
    output = GroqTextToSpeech("secret", client=client).synthesize(
        text, tmp_path / "merged.wav"
    )
    assert len(requests) >= 2
    payloads = [json.loads(request.content) for request in requests]
    assert all(len(payload["input"]) <= ORPHEUS_MAX_INPUT_CHARS for payload in payloads)
    with wave.open(str(output), "rb") as reader:
        assert reader.getnchannels() == 1
        assert reader.getsampwidth() == 2
        assert reader.getframerate() == 16_000
        assert reader.getnframes() == 80 * len(requests)


def test_groq_tts_400_reports_only_sanitized_provider_detail(tmp_path):
    def handler(request):
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": "invalid_request_error",
                    "message": "Input contains an unsupported character",
                }
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.groq.com/openai/v1"
    )
    with pytest.raises(RuntimeError) as error:
        GroqTextToSpeech("super-secret-key", client=client).synthesize(
            "Text", tmp_path / "a.wav"
        )
    message = str(error.value)
    assert "status 400" in message
    assert "invalid_request_error" in message
    assert "unsupported character" in message
    assert "super-secret-key" not in message
