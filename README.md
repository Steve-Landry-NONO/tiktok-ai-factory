# TikTok AI Factory V1

Usine locale et testable qui transforme une idée en vidéo TikTok prête à publier : scoring viral heuristique, script, storyboard, clips synthétiques, rendu FFmpeg, QA et métadonnées. **Le score est un outil de tri déterministe, pas une garantie de viralité.** La publication réelle reste hors V1.

## Installation

Prérequis : Python 3.12, `ffmpeg` et `ffprobe` accessibles dans `PATH`.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env  # facultatif; ne jamais committer ce fichier
python -m tiktok_factory.cli demo --output output/demo
```

Autres commandes :

```bash
python -m tiktok_factory.cli generate --idea "A city where gravity changes every midnight"
python -m tiktok_factory.cli validate output/demo/final.mp4
pytest -q
ruff check . && mypy
```

Le résultat local contient `final.mp4` (H.264, 1080x1920, 30 fps) et `metadata.json`. Le mock FFmpeg est gratuit et n'utilise aucune API.

## Architecture

Le domaine Pydantic et `FactoryPipeline` portent la logique. Les interfaces isolent LLM, génération vidéo, stockage, analytics et publication. n8n ne fait qu'appeler ces services. PostgreSQL/Supabase conserve toute la généalogie. Voir [ARCHITECTURE.md](ARCHITECTURE.md).

## Configuration et roadmap

Toutes les variables reconnues sont dans `.env.example`; aucune clé n'est requise en local. Les adaptateurs externes échouent explicitement tant qu'ils ne sont pas connectés à une API vérifiée. Roadmap : service HTTP, OpenAI structured outputs, Runway asynchrone, Supabase/RLS, import n8n puis TikTok Content Posting après revue d'accès.

## Intelligent V2 (Groq + Supabase)

The V2 keeps the offline media mocks while adding six structured agents and durable
Supabase genealogy. Offline mode needs no API credential:

```bash
python -m tiktok_factory.cli intelligent-demo --mode mock
```

Live mode requires server-side environment variables `GROQ_API_KEY`, `SUPABASE_URL`
and `SUPABASE_SECRET_KEY` plus FFmpeg. It uses `LLM_PROVIDER=groq`,
`openai/gpt-oss-120b` for Director/Creative Producer and
`openai/gpt-oss-20b` for the four independent judges:

```bash
python -m tiktok_factory.cli intelligent-demo --mode live --output output/intelligent_live
```

`LLM_PROVIDER=openai` is a future adapter selection point; it is intentionally rejected
until an official OpenAI implementation is configured. Never use a Supabase publishable
key for backend persistence.
