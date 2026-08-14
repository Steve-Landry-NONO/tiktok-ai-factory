# Project status

## DONE — WORKING_LOCAL
- Domaine typé complet, scoring pondéré/agrégé, confiance et quatre juges indépendants.
- Pipeline, budget, retry borné, providers mock, stockage/analytics mock, renderer/probe et QA structurées.
- CLI demo/generate/validate, migration Supabase, fixtures, 7 templates n8n, CI, documentation et tests.

## PARTIAL — READY_FOR_CREDENTIALS
- OpenAI, Runway, Supabase et TikTok ont des frontières documentées; leurs appels réels exigent SDK/API et credentials vérifiés.
- L'audio est détecté et validable; la V1 synthétique est volontairement silencieuse.

## BLOCKED — BLOCKED_EXTERNAL
- Publication TikTok hors périmètre V1; accès/application TikTok requis.
- Validation du 14 août 2026 : 23 tests non vidéo passent, ainsi que Ruff et mypy. La
  suite complète reste bloquée exclusivement par l'absence de FFmpeg/ffprobe. Les
  installations `pip` et `apt` ont été retentées, mais le proxy de l'environnement
  refuse les téléchargements avec HTTP 403. La CI installe FFmpeg avant les tests.
- Publication de branche/PR bloquée dans cette session : le remote GitHub est
  configuré, mais le proxy refuse le push avec HTTP 403 et `gh auth status`
  confirme qu'aucun compte GitHub n'est authentifié.

## NEXT
1. Exposer `FactoryPipeline` via un service HTTP authentifié et idempotent.
2. Connecter OpenAI puis Runway avec leurs SDK/docs actuels et tests contractuels.
3. Appliquer la migration Supabase, politiques RLS et stockage objet.
4. Importer n8n, configurer `FACTORY_API_URL`, webhooks et files d'erreur.
