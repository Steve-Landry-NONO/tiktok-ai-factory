# V4.1 — Render + n8n Cloud deployment

This guide deploys the V4 Factory API as a public HTTPS Docker service and connects it to n8n Cloud without exposing Groq, Runway, or Supabase credentials to n8n.

## 1. Deploy the Factory API on Render

The repository root contains `render.yaml` and `Dockerfile`.

Create a Render Blueprint from this repository and deploy the `main` branch after V4.1 is merged. The Blueprint uses:

- Docker runtime.
- `/healthz` health check.
- CI-gated auto deploys.
- a Free instance for the first mock integration test.
- `FACTORY_API_TOKEN` as a secret value entered in the Render dashboard.

Do not paste the token into GitHub, n8n workflow JSON, logs, or chat. Store it in a password manager and use the same token in the n8n Bearer Auth credential.

For the first mock test, provider secrets are not required. Before any live run, add the following Render secrets:

- `GROQ_API_KEY`
- `RUNWAY_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`

Also keep the existing model, provider, and budget environment variables aligned with `.env.example`.

After deployment, verify:

```text
GET https://<render-service>.onrender.com/healthz
```

Expected body:

```json
{"status":"ok","service":"tiktok-ai-factory"}
```

Copy the Render service base URL. Do not include `/v1/runs` yet.

## 2. Import the n8n Cloud workflow

Use `n8n/00_factory_orchestrator_v4_cloud.json` for n8n Cloud.

It differs from the self-hosted template in three important ways:

1. The incoming webhook uses Header Auth.
2. The webhook responds immediately (`onReceived`) so the caller is not held open while a long video job runs.
3. The Factory API call uses an n8n Bearer Auth credential instead of `$env`.

After import, configure two credentials in n8n Cloud.

### Incoming webhook credential

Create a **Header Auth** credential dedicated to the intake webhook, for example:

- Header name: `X-Factory-Webhook-Key`
- Header value: a separate random secret

Attach it to `V4 Cloud Intake Webhook`.

This prevents an unknown caller from using your n8n webhook to trigger paid generations.

### Factory API credential

Create an **HTTP Bearer Auth** credential containing the same `FACTORY_API_TOKEN` that is stored in Render.

Attach it to `Run Factory V4 Cloud`.

Then replace this placeholder in the HTTP Request node:

```text
https://YOUR-FACTORY-API.onrender.com/v1/runs
```

with:

```text
https://<your-render-service>.onrender.com/v1/runs
```

Do not put Groq, Runway, or Supabase secrets in n8n.

## 3. First end-to-end mock test

Keep the workflow unpublished while testing and use the Webhook node's test URL.

POST this JSON body with the incoming webhook Header Auth credential:

```json
{
  "idea": "A futuristic city where gravity reverses for one minute",
  "correlation_id": "n8n-cloud-mock-001",
  "mode": "mock",
  "video_provider": "synthetic",
  "postprocess": false
}
```

Expected behavior:

- n8n acknowledges the webhook quickly.
- the workflow continues running after the acknowledgement.
- the HTTP Request node calls the Render Factory API with Bearer Auth.
- no Groq or Runway paid generation is used.
- the Factory API returns a run result and creates a synthetic local output inside the Render instance.

For this first mock test, the output path only proves that the V4 control plane works end to end. Render's default filesystem is not the final durable media store.

## 4. Before the first live Runway request

Do not switch the request to `mode=live` until all of these are true:

- Render has Groq, Runway, and Supabase secrets configured.
- Supabase migration `orchestration_runs` is present.
- the mock n8n → Render → Factory API test passes.
- durable media storage is implemented or a temporary persistence strategy has been explicitly accepted.
- the incoming n8n webhook remains authenticated.

A live request keeps the existing V4 contract:

```json
{
  "idea": "One safe visual TikTok seed",
  "correlation_id": "daily-2026-08-14-slot-1",
  "mode": "live",
  "video_provider": "runway",
  "postprocess": true
}
```

Reuse of a `correlation_id` is handled server-side by the Supabase orchestration ledger to prevent duplicate paid generation.
