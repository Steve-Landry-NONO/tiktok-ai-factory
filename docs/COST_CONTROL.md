# Cost control
`BudgetPolicy` bloque avant génération si estimation + dépenses dépasse `MAX_COST_PER_VIDEO` ou `MAX_DAILY_GENERATION_COST`. Chaque job trace provider, modèle, estimation, réel et tentative. Le mock vaut zéro. En production, réserver le budget transactionnellement, réconcilier le coût réel, plafonner retries et alerter sur écart estimation/réel.
