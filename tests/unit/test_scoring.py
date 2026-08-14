import pytest
from tiktok_factory.scoring import confidence_score, decision_for, deterministic_dimensions, aggregate_scores
from tiktok_factory.domain.models import ScoreDecision

@pytest.mark.parametrize(('value','expected'), [(0,'REJECT'),(54.9,'REJECT'),(55,'EXPERIMENT'),(69.9,'EXPERIMENT'),(70,'CANDIDATE'),(80,'PRODUCE'),(90,'PRIORITY'),(100,'PRIORITY')])
def test_thresholds(value,expected): assert decision_for(value) == ScoreDecision(expected)
def test_confidence(): assert confidence_score([80,80,80]) == 1; assert confidence_score([80]) == .5
def test_independent_judges():
 d=deterministic_dimensions('why does a city change gravity at midnight?')
 with pytest.raises(ValueError): aggregate_scores([('same',d),('same',d)])
