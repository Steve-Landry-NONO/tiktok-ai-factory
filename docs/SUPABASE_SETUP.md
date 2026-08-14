# Supabase setup
Appliquer `supabase/migrations/0001_initial.sql`, puis le seed uniquement en développement. Activer RLS sur toutes les tables avant exposition : service backend seul en écriture, lecture par tenant/propriétaire, aucune policy anonyme. La service-role reste serveur uniquement. Stocker les objets dans un bucket privé et la base ne conserve que les clés de stockage.
