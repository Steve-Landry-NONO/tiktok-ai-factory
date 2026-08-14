# TikTok AI Factory

Usine testable qui transforme une idée en vidéo TikTok prête à publier : agents créatifs,
scoring viral multi-juges, script, storyboard, génération vidéo, rendu FFmpeg, QA,
persistance Supabase et métadonnées. **Le score viral est un outil de tri, jamais une
garantie de performance réelle.**

## Installation locale

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

Le mode synthétique produit `final.mp4` en H.264, 1080x1920, 30 fps et un
`metadata.json` sans appeler de service vidéo payant.

## Architecture

Le domaine Pydantic et `FactoryPipeline` portent la logique métier. Les interfaces isolent
LLM, génération vidéo, stockage, analytics et publication. PostgreSQL/Supabase conserve la
généalogie. n8n reste une couche d'orchestration et ne doit pas recopier les règles métier.
Voir [ARCHITECTURE.md](ARCHITECTURE.md).

## Intelligent V2 — Groq + Supabase

Le mode offline utilise six agents déterministes sans secret :

```bash
python -m tiktok_factory.cli intelligent-demo --mode mock
```

Le mode live utilise Groq pour Director, Creative Producer et quatre juges indépendants,
puis persiste le pipeline dans Supabase :

```bash
python -m tiktok_factory.cli intelligent-demo \
  --mode live \
  --video-provider synthetic \
  --output output/intelligent_live
```

Il exige `GROQ_API_KEY`, `SUPABASE_URL` et `SUPABASE_SECRET_KEY` côté serveur.

## Runway V3 — vraie génération vidéo IA

Le provider `RunwayProvider` remplace les clips synthétiques par de vrais clips générés
par Runway, puis réutilise le renderer/QA/persistance existants :

```bash
python -m tiktok_factory.cli intelligent-demo \
  --mode live \
  --video-provider runway \
  --output output/runway_live \
  --idea "A futuristic city where gravity reverses every midnight"
```

Ce mode exige aussi `RUNWAY_API_KEY` et constitue une opération payante. La configuration
par défaut utilise `gen4.5` en portrait `720:1280`; le renderer produit ensuite le profil
final TikTok 1080x1920. Le storyboard V3 est borné à 3-4 shots de 10 secondes maximum et
le pipeline vérifie le coût de l'ensemble d'une tentative avant de lancer le premier appel
Runway. Le workflow GitHub Actions manuel `Runway V3 Live Validation` permet le premier
test réel avec un plafond de dépense explicite.

La QA technique inspecte réellement le MP4. La QA créative actuelle reste un provider de
test déterministe et devra être remplacée par une revue visuelle IA avant l'automatisation
sans supervision.

## Configuration et suite

Toutes les variables reconnues sont documentées dans `.env.example`. Les secrets doivent
rester hors Git. `LLM_PROVIDER=openai` reste un futur point de sélection tant que l'adapter
OpenAI n'est pas configuré. Après validation du premier MP4 Runway réel, la prochaine étape
est l'exposition du pipeline via une API idempotente puis l'orchestration n8n et la file de
publication TikTok.
