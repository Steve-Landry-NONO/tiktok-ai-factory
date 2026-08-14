-- V4 orchestration idempotency ledger.
-- Server-role access only; RLS is intentionally enabled without public policies.

create table if not exists public.orchestration_runs (
    correlation_id text primary key,
    status text not null,
    request jsonb not null default '{}'::jsonb,
    result jsonb,
    error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_orchestration_runs_status
    on public.orchestration_runs(status);

alter table public.orchestration_runs enable row level security;
