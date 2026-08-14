import statistics

from tiktok_factory.domain.models import ScoreDecision, ViralDimensions, ViralScore

WEIGHTS = {"hook": 20, "curiosity_gap": 15, "visual_novelty": 15,
           "retention_potential": 15, "emotional_response": 10, "shareability": 10,
           "comment_potential": 5, "loop_potential": 5, "series_potential": 5}


def decision_for(total: float) -> ScoreDecision:
    if total < 55: return ScoreDecision.REJECT
    if total < 70: return ScoreDecision.EXPERIMENT
    if total < 80: return ScoreDecision.CANDIDATE
    if total < 90: return ScoreDecision.PRODUCE
    return ScoreDecision.PRIORITY


def deterministic_dimensions(concept: str) -> ViralDimensions:
    """Transparent heuristic baseline; useful for tests, never a virality guarantee."""
    text = concept.lower()
    words = text.split()
    question = "?" in text or any(x in words for x in ("why", "how", "what", "secret"))
    vivid = sum(x in text for x in ("city", "gravity", "midnight", "transforms", "impossible", "world"))
    emotion = sum(x in text for x in ("love", "fear", "shock", "amazing", "surprise"))
    specificity = min(len(set(words)) / 12, 1)
    values = {
        "hook": min(20, 7 + 6 * question + 7 * specificity),
        "curiosity_gap": min(15, 4 + 6 * question + vivid),
        "visual_novelty": min(15, 3 + 2.5 * vivid),
        "retention_potential": min(15, 5 + 4 * question + 3 * specificity),
        "emotional_response": min(10, 3 + 2 * emotion + vivid / 2),
        "shareability": min(10, 3 + vivid + 2 * specificity),
        "comment_potential": min(5, 1 + 2 * question + specificity),
        "loop_potential": min(5, 1 + (2 if "midnight" in text or "loop" in text else 0) + specificity),
        "series_potential": min(5, 1 + (2 if "world" in text or "city" in text else 0) + specificity),
    }
    return ViralDimensions(**values)


def confidence_score(totals: list[float]) -> float:
    if not totals: raise ValueError("at least one independent judge is required")
    if len(totals) == 1: return 0.5
    return round(max(0.0, 1 - statistics.pstdev(totals) / 50), 3)


def aggregate_scores(evaluations: list[tuple[str, ViralDimensions]]) -> ViralScore:
    if len({name for name, _ in evaluations}) != len(evaluations):
        raise ValueError("judges must be independent and uniquely named")
    if not evaluations: raise ValueError("evaluations cannot be empty")
    dims = ViralDimensions(**{
        field: statistics.fmean(getattr(score, field) for _, score in evaluations)
        for field in WEIGHTS
    })
    total = round(dims.total, 2)
    return ViralScore(dimensions=dims, total=total, decision=decision_for(total),
                      confidence=confidence_score([s.total for _, s in evaluations]),
                      judges=[name for name, _ in evaluations])

