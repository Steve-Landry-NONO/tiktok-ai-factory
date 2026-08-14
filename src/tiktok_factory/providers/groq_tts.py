"""Groq text-to-speech adapter (no calls are made until ``synthesize``)."""

from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Any
import re
import time
import wave

import httpx

from tiktok_factory.providers.base import TextToSpeechProvider


ORPHEUS_ENGLISH_MODEL = "canopylabs/orpheus-v1-english"
DEFAULT_ORPHEUS_VOICE = "troy"
ORPHEUS_MAX_INPUT_CHARS = 200
_TTS_PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "—": "-",
        "–": "-",
        "‑": "-",
        "‒": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "\u00a0": " ",
    }
)


def normalize_tts_text(text: str) -> str:
    """Normalize typography that can be rejected by speech provider input validation."""
    return " ".join(text.translate(_TTS_PUNCTUATION_TRANSLATION).split())


def split_tts_text(text: str, limit: int = ORPHEUS_MAX_INPUT_CHARS) -> list[str]:
    """Split narration into provider-safe chunks without breaking normal words."""
    clean = normalize_tts_text(text)
    if not clean:
        raise ValueError("narration must not be empty")
    if limit < 1:
        raise ValueError("TTS chunk limit must be positive")
    if len(clean) <= limit:
        return [clean]

    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", clean) if part.strip()]
    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current:
            chunks.append(current)
            current = ""

    for sentence in sentences:
        if len(sentence) <= limit:
            candidate = f"{current} {sentence}".strip()
            if len(candidate) <= limit:
                current = candidate
            else:
                flush()
                current = sentence
            continue

        flush()
        words = sentence.split()
        piece = ""
        for word in words:
            if len(word) > limit:
                if piece:
                    chunks.append(piece)
                    piece = ""
                chunks.extend(word[start:start + limit] for start in range(0, len(word), limit))
                continue
            candidate = f"{piece} {word}".strip()
            if len(candidate) <= limit:
                piece = candidate
            else:
                chunks.append(piece)
                piece = word
        if piece:
            current = piece
    flush()
    return chunks


def _safe_error_detail(response: httpx.Response) -> str:
    """Return only provider error code/message, never headers, auth, or request payload."""
    try:
        body = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    error = body.get("error")
    if not isinstance(error, dict):
        return ""
    code = str(error.get("code", "")).strip()
    message = " ".join(str(error.get("message", "")).split()).strip()
    if len(message) > 240:
        message = message[:237] + "..."
    details = "; ".join(part for part in (f"code={code}" if code else "", message) if part)
    return details


class GroqTextToSpeech(TextToSpeechProvider):
    base_url = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = ORPHEUS_ENGLISH_MODEL,
        voice: str = DEFAULT_ORPHEUS_VOICE,
        client: httpx.Client | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not api_key:
            raise ValueError("GROQ_API_KEY is required for narration")
        self._api_key, self.model, self.voice = api_key, model, voice
        self._client = client or httpx.Client(base_url=self.base_url, timeout=timeout)
        self.max_retries, self._sleep = max_retries, sleep

    def _request_chunk(self, text: str) -> bytes:
        payload = {
            "model": self.model,
            "voice": self.voice,
            "input": text,
            "response_format": "wav",
        }
        response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.post(
                    "/audio/speech",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    raise RuntimeError("Groq TTS network request failed after retries") from exc
                self._sleep(2**attempt)
                continue
            if response.status_code in (401, 403):
                raise RuntimeError("Groq TTS authentication failed")
            if (response.status_code == 429 or response.status_code >= 500) and attempt < self.max_retries:
                self._sleep(2**attempt)
                continue
            if response.is_error:
                detail = _safe_error_detail(response)
                suffix = f": {detail}" if detail else ""
                raise RuntimeError(f"Groq TTS failed with status {response.status_code}{suffix}")
            return response.content
        raise RuntimeError("Groq TTS failed after retries")

    @staticmethod
    def _merge_wav(parts: list[bytes], destination: Path) -> None:
        params: Any = None
        frames: list[bytes] = []
        for part in parts:
            try:
                with wave.open(BytesIO(part), "rb") as reader:
                    current = reader.getparams()
                    if params is None:
                        params = current
                    elif (
                        current.nchannels != params.nchannels
                        or current.sampwidth != params.sampwidth
                        or current.framerate != params.framerate
                        or current.comptype != params.comptype
                    ):
                        raise RuntimeError("Groq TTS returned incompatible WAV chunks")
                    frames.append(reader.readframes(reader.getnframes()))
            except (EOFError, wave.Error) as exc:
                raise RuntimeError("Groq TTS returned an invalid WAV chunk") from exc
        if params is None:
            raise RuntimeError("Groq TTS returned no audio")
        with wave.open(str(destination), "wb") as writer:
            writer.setnchannels(params.nchannels)
            writer.setsampwidth(params.sampwidth)
            writer.setframerate(params.framerate)
            writer.setcomptype(params.comptype, params.compname)
            for frame_data in frames:
                writer.writeframes(frame_data)

    def synthesize(self, text: str, destination: Path) -> Path:
        chunks = split_tts_text(text)
        audio_parts = [self._request_chunk(chunk) for chunk in chunks]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if len(audio_parts) == 1:
            destination.write_bytes(audio_parts[0])
        else:
            self._merge_wav(audio_parts, destination)
        return destination
