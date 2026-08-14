from uuid import uuid4

from tiktok_factory.qa.reviews import review_audio_probe


def test_audio_qa_passes_coherent_stream():
    data = {"format": {"duration": "4"}, "streams": [
        {"codec_type": "video", "duration": "4"},
        {"codec_type": "audio", "codec_name": "aac", "duration": "4"},
    ]}
    assert review_audio_probe(uuid4(), data).outcome == "PASS"


def test_audio_qa_allows_small_aac_container_duration_drift():
    data = {"format": {"duration": "20.13"}, "streams": [
        {"codec_type": "video", "duration": "20.13"},
        {"codec_type": "audio", "codec_name": "aac", "duration": "19.35"},
    ]}
    review = review_audio_probe(uuid4(), data)
    assert review.outcome == "PASS"
    assert review.checks["duration_coherent"]


def test_audio_qa_rejects_large_duration_gap_and_reports_values():
    data = {"format": {"duration": "20.13"}, "streams": [
        {"codec_type": "video", "duration": "20.13"},
        {"codec_type": "audio", "codec_name": "aac", "duration": "17.0"},
    ]}
    review = review_audio_probe(uuid4(), data)
    assert review.outcome == "FAIL"
    assert not review.checks["duration_coherent"]
    assert any("audio=17.000s" in item for item in review.diagnostics)


def test_audio_qa_fails_missing_required_stream():
    data = {"format": {"duration": "4"}, "streams": [{"codec_type": "video", "duration": "4"}]}
    review = review_audio_probe(uuid4(), data)
    assert review.outcome == "FAIL"
    assert not review.checks["audio_stream"]
