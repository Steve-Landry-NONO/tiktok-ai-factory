# Project status

## DONE — V2 LIVE VALIDATED
- V1 typed scoring, bounded retry/budget, synthetic provider, FFmpeg renderer and QA.
- V2 Director, Creative Producer and four independent structured judges.
- Groq OpenAI-compatible provider with strict schemas and bounded error handling.
- Six real Groq agent calls validated in GitHub Actions.
- Supabase live persistence and read-after-write validated with complete genealogy.
- Synthetic final MP4 validated by FFmpeg/ffprobe as H.264, 1080x1920, 30 fps.
- Deterministic correlation-based IDs and additive migrations 0002/0003.
- Offline mocks and HTTP-mocked provider/storage tests remain deterministic in CI.

## IMPLEMENTED — V3 RUNWAY READY FOR PAID LIVE VALIDATION
- Real `RunwayProvider` implemented behind `VideoGenerationProvider`.
- Gen-4.5 text-to-video path uses portrait 720x1280, asynchronous tasks and immediate
  durable download of provider output.
- Storyboard generation is bounded to 3-4 shots, each at most 10 seconds.
- Dynamic per-shot cost estimation and full-attempt budget preflight occur before paid calls.
- Runway authentication, network/transient retry, polling, terminal task errors and downloads
  are covered by mocked tests.
- Manual GitHub Actions workflow `Runway V3 Live Validation` exists with an explicit USD
  generation ceiling and uploads the individual clips plus final rendered MP4.

## EXTERNAL GATES
- `RUNWAY_API_KEY` and funded Runway API credits are required before the first paid V3 run.
- OpenAI API account permissions remain independent and do not block the Groq-based pipeline.
- Current creative video QA is deterministic test QA, not yet a vision-model inspection of the
  generated Runway frames.

## NEXT
1. Keep CI green for the V3 implementation.
2. Configure `RUNWAY_API_KEY` as a GitHub Actions repository secret and fund API credits.
3. Explicitly launch one Runway validation under the configured hard spend ceiling.
4. Verify Runway clips, final MP4, Supabase genealogy and technical QA.
5. Replace mock creative QA with real visual QA before unattended production.
6. Expose the factory through an authenticated idempotent API, then wire n8n scheduling,
   approval/publish queue and growth feedback.
