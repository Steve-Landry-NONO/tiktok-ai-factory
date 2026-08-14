# Security
Les secrets viennent exclusivement de l'environnement; `.env` est ignoré. Utiliser un coffre en production, rotation, moindre privilège, logs expurgés, URLs signées courtes et validation des médias. Scanner avant chaque release avec `git grep` et un scanner dédié (gitleaks recommandé). Ne jamais exposer la service-role Supabase au navigateur ou à n8n non isolé.
