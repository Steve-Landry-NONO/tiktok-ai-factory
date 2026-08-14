# Contributing
Utilisez Python 3.12. Installez `.[dev]`, lancez `ruff check .`, `mypy` et `pytest -q`. Aucun test ne doit appeler une API payante. Ne committez jamais `.env`, vidéo générée ou credential. Toute évolution de provider nécessite un test contractuel et une documentation de coût/retry.
