import json
from pathlib import Path
from tiktok_factory.scoring import deterministic_dimensions,decision_for

def test_golden_heuristic_dataset():
 for row in json.loads(Path('tests/golden/ideas.json').read_text()):
  assert decision_for(deterministic_dimensions(row['idea']).total).value==row['decision'], row
