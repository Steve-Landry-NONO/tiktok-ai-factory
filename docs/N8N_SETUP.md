# n8n V4 orchestration

## Principle

n8n is the control plane, not the business-logic runtime. It must not call Groq,
Runway or Supabase directly. The Python service owns provider credentials, cost
controls, idempotency, media generation, V3.1 post-production and QA.

The seven historical files `01_*.json` through `07_*.json` are V1 placeholders.
They are kept for reference but their old `/director`, `/video-factory`, etc.
routes are not production contracts.

The V4 entry point is:

- `POST /v1/runs` on the Factory API.
- `n8n/00_factory_orchestrator_v4.json` as the first importable workflow.
- `correlation_id` is mandatory and is the idempotency key.

## Required environment

Factory API:

- `FACTORY_API_TOKEN`: long random bearer token.
- `FACTORY_OUTPUT_ROOT`: local work directory, default `output/api`.
- `GROQ_API_KEY`.
- `SUPABASE_URL`.
- `SUPABASE_SECRET_KEY`.
- `RUNWAY_API_KEY` for real video generation.
- existing provider and budget variables from `.env.example`.

n8n:

- `FACTORY_API_URL`: HTTPS URL of the deployed Factory API.
- `FACTORY_API_TOKEN`: same bearer token, stored as an n8n secret/credential.

Do not export provider secrets into n8n.

## Start the API locally

```bash
python -m pip install -e '.[dev]'
export FACTORY_API_TOKEN='replace-with-a-long-random-secret'
tiktok-factory-api
```

Health check:

```bash
curl http://localhost:8000/healthz
```

A mock request without paid providers:

```bash
curl -X POST http://localhost:8000/v1/runs \
  -H "Authorization: Bearer $FACTORY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "idea": "A futuristic city where gravity reverses for one minute",
    "correlation_id": "smoke-2026-08-14-1",
    "mode": "mock",
    "video_provider": "synthetic",
    "postprocess": false
  }'
```

## Live request contract

```json
{
  "idea": "One safe visual TikTok seed",
  "correlation_id": "daily-2026-08-14-slot-1",
  "mode": "live",
  "video_provider": "runway",
  "postprocess": true
}
```

A live request first reserves `correlation_id` in the Supabase
`orchestration_runs` table. Replaying the same ID returns the stored state/result
instead of starting another paid generation. This is the protection layer for
n8n retries, duplicate webhook delivery and operator double-clicks.

Apply `supabase/migrations/0004_orchestration_runs.sql` before the first live V4 run.

## Import the V4 workflow

Import `n8n/00_factory_orchestrator_v4.json`.

It exposes a POST webhook and forwards `body` to `/v1/runs` with bearer auth.
The HTTP Request timeout is intentionally long because V4.0 is synchronous.
Do not enable blind HTTP retries; idempotency is server-side, but a duplicate
execution should still be observable.

For n8n versions where `$env` is unavailable, replace the Authorization header
expression with an n8n Header Auth credential. Verify node `typeVersion` values
against the deployed n8n version after import.

## Next V4 slices

V4.0 establishes the authenticated, idempotent control plane.
The following slices should be added only after this API is deployed and smoke-tested:

1. Trend intake + deterministic daily correlation IDs.
2. Approval queue and notification workflow.
3. Durable media storage rather than runner-local paths.
4. TikTok Posting API integration behind human approval.
5. Metrics ingestion and growth-learning loop.
