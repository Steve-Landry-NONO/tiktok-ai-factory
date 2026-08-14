# Architecture V1

## Flux et frontières

`ContentIdea → ViralScore → Script → Storyboard → GenerationJob/MediaAsset → Video → QAReview → READY_TO_PUBLISH`. `FactoryPipeline` est le service applicatif synchrone. Les modèles Pydantic interdisent les champs inconnus; les enums centralisent états et décisions. Les agents ont chacun un schéma de sortie strict et un prompt versionné.

Les ports `LLMProvider`, `VideoGenerationProvider`, `StorageProvider`, `AnalyticsProvider` et `PublishingProvider` séparent le métier des infrastructures. Les mocks sont fonctionnels. OpenAI/Runway sont des points de connexion explicites sans endpoint inventé. Supabase et TikTok seront ajoutés derrière les mêmes frontières.

## Vidéo, retry, coût et QA

Le profil `tiktok_vertical_v1` normalise à 1080x1920, 30 fps, H.264/yuv420p. Le générateur produit trois clips gratuits; le renderer les concatène et superpose le hook. L'absence de FFmpeg/ffprobe produit une exception explicite. L'audio est facultatif en V1; le renderer est prêt à évoluer vers une branche audio AAC/loudnorm lorsque narration ou musique existe.

`BudgetPolicy` autorise avant chaque appel selon les limites vidéo et journalière; un
`CostLedger` injectable fournit et enregistre la consommation quotidienne.
`RetryPolicy` pilote réellement la boucle generation/render/QA, conserve les
diagnostics et devient `FAILED_PERMANENTLY` après le nombre borné de retries. Chaque
job porte son numéro de tentative. La QA créative est fournie par un
`CreativeQAProvider` indépendant et injectable; elle applique PASS ≥85, RETRYABLE
75–84, FAIL <75. La QA technique inspecte présence, taille, probe, codec, résolution,
ratio, durée, fps, audio configurable et corruption.

## Données et orchestration

La migration relie source/idea/script/storyboard/shots/jobs/assets/video/QA/publication/metrics. JSONB est limité aux sorties structurées, contrôles et diagnostics. Les templates n8n déclenchent et appellent une future API `FACTORY_API_URL`; ils ne copient pas les règles métier. En production : workers idempotents, file d'attente, webhooks providers, stockage objet et transactions de statut.

## V2 intelligent orchestration

`IntelligentPipeline` calls Director and Creative Producer with the primary model, then
four independent judges with the judge model. Every call uses a strict Pydantic JSON
schema and is captured as a non-secret `AgentRun`. Groq is behind a structured-provider
protocol, so an OpenAI adapter can be selected later without changing orchestration.
Bounded exponential backoff applies only to network, 429 and server failures; 401 is
permanent.

The Supabase REST repository uses only a server secret, upserts deterministic genealogy
IDs, and verifies the idea with a read-after-write. A stable correlation ID derives the
idea, script, storyboard, shot, job, asset, video and QA IDs, making n8n replays
convergent. The original migration remains immutable; V2 schema changes are in 0002 and
0003.
