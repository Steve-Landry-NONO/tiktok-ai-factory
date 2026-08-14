import json
from pathlib import Path


def test_migration_tables():
    sql = Path("supabase/migrations/0001_initial.sql").read_text()
    for table in (
        "content_ideas",
        "scripts",
        "storyboards",
        "storyboard_shots",
        "generation_jobs",
        "media_assets",
        "videos",
        "qa_reviews",
        "publications",
        "performance_metrics",
        "experiments",
        "agent_runs",
    ):
        assert f"create table {table}" in sql


def test_n8n_json_templates():
    paths = list(Path("n8n").glob("*.json"))
    names = {path.name for path in paths}
    expected = {
        "00_factory_orchestrator_v4.json",
        "01_director.json",
        "02_trend_scout.json",
        "03_content_factory.json",
        "04_video_factory.json",
        "05_qa.json",
        "06_publish_queue.json",
        "07_growth_loop.json",
    }
    assert expected <= names
    for path in paths:
        data = json.loads(path.read_text())
        assert data["nodes"] and data["connections"]


def test_all_public_tables_enable_rls_without_permissive_policy():
    sql = Path("supabase/migrations/0001_initial.sql").read_text().lower()
    tables = (
        "content_ideas",
        "scripts",
        "storyboards",
        "storyboard_shots",
        "generation_jobs",
        "media_assets",
        "videos",
        "qa_reviews",
        "publications",
        "performance_metrics",
        "experiments",
        "agent_runs",
    )
    for table in tables:
        assert f"alter table public.{table} enable row level security" in sql
    assert "using (true)" not in sql


def test_additive_idempotency_migration():
    path = Path("supabase/migrations/0003_add_pipeline_idempotency.sql")
    sql = path.read_text().lower()
    assert "correlation_id" in sql and "unique index" in sql


def test_v4_orchestration_migration_is_server_role_only():
    path = Path("supabase/migrations/0004_orchestration_runs.sql")
    sql = path.read_text().lower()
    assert "create table if not exists public.orchestration_runs" in sql
    assert "correlation_id text primary key" in sql
    assert "alter table public.orchestration_runs enable row level security" in sql
    assert "using (true)" not in sql
