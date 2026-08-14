-- A stable correlation key makes orchestrator replays converge on one idea.
alter table public.content_ideas add column if not exists correlation_id text;
create unique index if not exists content_ideas_correlation_id_uidx
  on public.content_ideas(correlation_id) where correlation_id is not null;
