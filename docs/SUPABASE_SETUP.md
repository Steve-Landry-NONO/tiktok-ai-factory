# Supabase setup

Apply migrations in order. `0001_initial.sql` creates the secure RLS-enabled schema,
`0002_add_foreign_key_indexes.sql` optimizes genealogy joins, and
`0003_add_pipeline_idempotency.sql` adds the unique correlation key. No permissive RLS
policy is created.

Live backend persistence requires only `SUPABASE_URL` and `SUPABASE_SECRET_KEY`. The
secret key/service role is exclusively server-side: never expose it to a browser, public
n8n instance, logs, workflow exports, or client bundles. The repository upserts stable
domain UUIDs and performs an idea read-after-write. A future deployed orchestrator must
run in a private environment with its credential stored in a secrets manager.
