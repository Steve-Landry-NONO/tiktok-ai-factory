import json
from pathlib import Path

def test_migration_tables():
 sql=Path('supabase/migrations/0001_initial.sql').read_text()
 for table in ('content_ideas','scripts','storyboards','storyboard_shots','generation_jobs','media_assets','videos','qa_reviews','publications','performance_metrics','experiments','agent_runs'): assert f'create table {table}' in sql
def test_n8n_json_templates():
 for p in Path('n8n').glob('*.json'):
  data=json.loads(p.read_text()); assert data['nodes'] and data['connections']
 assert len(list(Path('n8n').glob('*.json')))==7
