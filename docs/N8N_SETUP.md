# n8n setup
Les sept fichiers sont des templates importables fondés sur Manual Trigger + HTTP Request. Définir `FACTORY_API_URL` dans un environnement/credential n8n non exporté, remplacer le déclencheur selon le déploiement et configurer authentification, timeout, backoff et error workflow. Vérifier `typeVersion` avec la version n8n déployée. La logique demeure dans le service Python.
