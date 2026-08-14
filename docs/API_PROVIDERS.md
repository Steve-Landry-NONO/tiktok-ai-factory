# API providers

## Groq — implemented

Set `LLM_PROVIDER=groq` and keep `GROQ_API_KEY` in a server secret store. The provider
uses Groq's OpenAI-compatible base URL (`https://api.groq.com/openai/v1`) and strict JSON
schema responses. Defaults are `openai/gpt-oss-120b` for Director/Creative Producer and
`openai/gpt-oss-20b` for judges. Authentication failures are never retried; timeouts,
429 and 5xx use bounded exponential backoff. Errors and agent-run records never contain
credentials or Authorization headers.

## Future OpenAI selection

`LLM_PROVIDER=openai` is reserved by the provider boundary but intentionally fails until
an official OpenAI adapter is implemented and verified. No endpoint is invented.

Runway and TikTok remain out of scope. Their existing boundaries are placeholders only.
