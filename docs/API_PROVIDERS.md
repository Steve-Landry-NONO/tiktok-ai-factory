# API providers

## Groq — implemented and live-validated

Set `LLM_PROVIDER=groq` and keep `GROQ_API_KEY` in a server secret store. The provider
uses Groq's OpenAI-compatible API and strict JSON schema responses. Defaults are
`openai/gpt-oss-120b` for Director/Creative Producer and `openai/gpt-oss-20b` for judges.
Authentication failures are never retried; timeouts, 429 and 5xx use bounded exponential
backoff. Errors and agent-run records never contain credentials or Authorization headers.

## Runway — implemented, paid live validation gated

Set `VIDEO_PROVIDER=runway` and keep `RUNWAY_API_KEY` only in a server-side secret store.
The V3 provider uses Runway's asynchronous text-to-video API with `gen4.5`, portrait
`720:1280`, and API version `2024-11-06`. It creates one task per storyboard shot, polls
at intervals of at least five seconds with jitter, then immediately downloads the
successful output URL to local durable storage before rendering.

Storyboard generation is constrained to 3-4 shots of at most 10 seconds each. Runway
billable duration is normalized to integer 2-10 second clips. `estimate_cost()` calculates
per-shot cost before a provider call and `FactoryPipeline` preflights the full attempt
before spending anything. The first manual live workflow is hard-capped by
`MAX_COST_PER_VIDEO` and `MAX_DAILY_GENERATION_COST`.

The output clips are normalized by the existing FFmpeg renderer into the final TikTok
profile (1080x1920, H.264, 30 fps) and then pass technical QA. Current creative QA remains
a deterministic test provider; it is not yet a vision-model review of Runway output.

## Future OpenAI selection

`LLM_PROVIDER=openai` is reserved by the provider boundary but intentionally fails until
an official OpenAI adapter is implemented and verified. No endpoint is invented.

TikTok publishing remains outside the current V3 milestone; n8n orchestration follows the
first successful real Runway MP4.
