create extension if not exists pgcrypto;
create type pipeline_status as enum ('IDEA_CREATED','IDEA_SCORED','IDEA_REJECTED','SCRIPT_CREATED','STORYBOARD_CREATED','GENERATION_PENDING','GENERATING','GENERATION_FAILED','RENDER_PENDING','RENDERING','QA_PENDING','QA_FAILED','RETRY_REQUIRED','READY_TO_PUBLISH','FAILED_PERMANENTLY');
create type qa_outcome as enum ('PASS','RETRYABLE','FAIL');
create table content_ideas (id uuid primary key default gen_random_uuid(), concept text not null check(length(concept)>=3), source text not null, creator text not null, status pipeline_status not null default 'IDEA_CREATED', viral_score numeric check(viral_score between 0 and 100), created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table scripts (id uuid primary key default gen_random_uuid(), idea_id uuid not null references content_ideas(id) on delete cascade, hook text not null, narration text not null, call_to_action text not null, created_at timestamptz not null default now());
create table storyboards (id uuid primary key default gen_random_uuid(), script_id uuid not null references scripts(id) on delete cascade, created_at timestamptz not null default now());
create table storyboard_shots (id uuid primary key default gen_random_uuid(), storyboard_id uuid not null references storyboards(id) on delete cascade, shot_number integer not null check(shot_number>0), concept text not null, caption text not null default '', duration_seconds numeric not null check(duration_seconds>0), unique(storyboard_id,shot_number));
create table generation_jobs (id uuid primary key default gen_random_uuid(), shot_id uuid not null references storyboard_shots(id), provider text not null, model text not null, estimated_cost numeric not null check(estimated_cost>=0), actual_cost numeric check(actual_cost>=0), attempt integer not null default 1 check(attempt>0), status pipeline_status not null, created_at timestamptz not null default now());
create table media_assets (id uuid primary key default gen_random_uuid(), job_id uuid not null references generation_jobs(id), storage_key text not null, media_type text not null, duration_seconds numeric check(duration_seconds>0), created_at timestamptz not null default now());
create table videos (id uuid primary key default gen_random_uuid(), storyboard_id uuid not null references storyboards(id), storage_key text not null, profile text not null, status pipeline_status not null, created_at timestamptz not null default now());
create table qa_reviews (id uuid primary key default gen_random_uuid(), video_id uuid not null references videos(id) on delete cascade, kind text not null check(kind in ('technical','creative')), outcome qa_outcome not null, score numeric check(score between 0 and 100), checks jsonb not null default '{}', diagnostics jsonb not null default '[]', created_at timestamptz not null default now());
create table publications (id uuid primary key default gen_random_uuid(), video_id uuid not null references videos(id), provider text not null, external_id text, published_at timestamptz, created_at timestamptz not null default now());
create table performance_metrics (id uuid primary key default gen_random_uuid(), publication_id uuid not null references publications(id) on delete cascade, views bigint not null check(views>=0), likes bigint not null check(likes>=0), comments bigint not null check(comments>=0), shares bigint not null check(shares>=0), average_watch_time numeric not null check(average_watch_time>=0), completion_rate numeric not null check(completion_rate between 0 and 1), followers_gained integer not null, measured_at timestamptz not null default now());
create table experiments (id uuid primary key default gen_random_uuid(), name text not null, cohort text not null, format text, hook_type text, duration_bucket text, creative_family text, publication_time time, created_at timestamptz not null default now());
create table agent_runs (id uuid primary key default gen_random_uuid(), agent text not null, provider text not null, input jsonb not null, output jsonb not null, created_at timestamptz not null default now());
create index content_ideas_status_idx on content_ideas(status); create index scripts_idea_idx on scripts(idea_id); create index jobs_shot_idx on generation_jobs(shot_id); create index videos_status_idx on videos(status); create index metrics_publication_idx on performance_metrics(publication_id,measured_at desc); create index agent_runs_agent_idx on agent_runs(agent,created_at desc);

-- Secure-by-default Supabase posture. No anonymous/authenticated policies are
-- created until the product defines an end-user authorization model. The trusted
-- backend uses the service_role credential exclusively in a private server context.
alter table public.content_ideas enable row level security;
alter table public.scripts enable row level security;
alter table public.storyboards enable row level security;
alter table public.storyboard_shots enable row level security;
alter table public.generation_jobs enable row level security;
alter table public.media_assets enable row level security;
alter table public.videos enable row level security;
alter table public.qa_reviews enable row level security;
alter table public.publications enable row level security;
alter table public.performance_metrics enable row level security;
alter table public.experiments enable row level security;
alter table public.agent_runs enable row level security;
