# Supabase setup

Apply `supabase/migrations/0001_initial.sql`, then use the seed only in development.
The migration enables RLS on every table and intentionally creates no permissive
anonymous or authenticated policy. Consequently, public API roles cannot access the
tables until the project defines an explicit end-user authorization model.

The backend/orchestrator may use the Supabase `service_role` credential to perform
trusted server operations. Keep that credential exclusively in a server-side secret
store: never expose it to a browser, a public n8n instance, logs, workflow exports, or
client bundles. Use a private bucket and store only object keys in the database.
