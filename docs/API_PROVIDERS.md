# API providers
- **OpenAI**: implémenter `LLMProvider.structured` avec le SDK officiel actuel et les JSON schemas Pydantic; timeout, request ID et coût.
- **Runway**: implémenter création/poll/cancel derrière `VideoGenerationProvider` après vérification de la documentation et des modèles disponibles.
- **Supabase**: implémenter `StorageProvider` et repositories, URLs signées et RLS.
- **TikTok**: implémenter `PublishingProvider` seulement après approbation Content Posting, OAuth et revue des scopes.
Aucun endpoint fictif n'est présent. Les mocks restent les doubles de test CI et tous les adaptateurs réels doivent gérer idempotence, rate limits et erreurs structurées.
