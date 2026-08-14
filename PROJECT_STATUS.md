# Project status

## DONE — WORKING_LOCAL
- V1 typed scoring, bounded retry/budget, synthetic provider, FFmpeg renderer and QA.
- V2 Director, Creative Producer and four independent structured judges.
- Groq OpenAI-compatible provider with strict schemas and bounded error handling.
- Supabase repository mapping complete genealogy plus agent runs and read-after-write.
- Deterministic correlation-based IDs and additive migrations 0002/0003.
- Offline intelligent mocks and HTTP-mocked Groq/Supabase tests.

## PARTIAL — READY_FOR_CREDENTIALS
- `LLM_PROVIDER=groq` is implemented; `LLM_PROVIDER=openai` is a documented future adapter.
- Live CLI is implemented but requires all three live secrets and FFmpeg.

## BLOCKED — BLOCKED_EXTERNAL
- This sandbox exposes `SUPABASE_URL`, but not `SUPABASE_SECRET_KEY` or `GROQ_API_KEY`.
- FFmpeg/ffprobe remain unavailable and external downloads are rejected by the proxy.
- Consequently no Groq call, Supabase write/read, live MP4, remote CI or PR can be claimed.

## NEXT
1. Supply live server secrets to the execution environment without logging them.
2. Run the live intelligent demo and preserve its Supabase idea row.
3. Push this branch, observe GitHub Actions, and open the unmerged PR to `main`.
