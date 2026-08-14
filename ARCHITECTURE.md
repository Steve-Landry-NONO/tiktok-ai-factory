# Architecture V1

## Flux et frontières

`ContentIdea → ViralScore → Script → Storyboard → GenerationJob/MediaAsset → Video → QAReview → READY_TO_PUBLISH`. `FactoryPipeline` est le service applicatif synchrone. Les modèles Pydantic interdisent les champs inconnus; les enums centralisent états et décisions. Les agents ont chacun un schéma de sortie strict et un prompt versionné.

Les ports `LLMProvider`, `VideoGenerationProvider`, `StorageProvider`, `AnalyticsProvider` et `PublishingProvider` séparent le métier des infrastructures. Les mocks sont fonctionnels. OpenAI/Runway sont des points de connexion explicites sans endpoint inventé. Supabase et TikTok seront ajoutés derrière les mêmes frontières.

## Vidéo, retry, coût et QA

Le profil `tiktok_vertical_v1` normalise à 1080x1920, 30 fps, H.264/yuv420p. Le générateur produit trois clips gratuits; le renderer les concatène et superpose le hook. L'absence de FFmpeg/ffprobe produit une exception explicite. L'audio est facultatif en V1; le renderer est prêt à évoluer vers une branche audio AAC/loudnorm lorsque narration ou musique existe.

`BudgetPolicy` autorise avant appel selon limites vidéo/journalière. `RetryPolicy` trace les diagnostics et devient `FAILED_PERMANENTLY` après le nombre borné de retries. La QA technique inspecte présence, taille, probe, codec, résolution, ratio, durée, fps, audio configurable et corruption. La QA créative applique PASS ≥85, RETRYABLE 75–84, FAIL <75.

## Données et orchestration

La migration relie source/idea/script/storyboard/shots/jobs/assets/video/QA/publication/metrics. JSONB est limité aux sorties structurées, contrôles et diagnostics. Les templates n8n déclenchent et appellent une future API `FACTORY_API_URL`; ils ne copient pas les règles métier. En production : workers idempotents, file d'attente, webhooks providers, stockage objet et transactions de statut.
