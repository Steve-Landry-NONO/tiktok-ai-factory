from dataclasses import replace

from tiktok_factory.pipeline.typography import render_text_card
from tiktok_factory.qa.reviews import review_text_layout
from uuid import uuid4


def test_long_hook_wraps_and_stays_in_safe_zone(tmp_path):
    overlay = render_text_card(
        "This surprisingly long hook must wrap cleanly inside a vertical TikTok video",
        tmp_path / "hook.png", start_time=0.2, end_time=3.0, y=180,
    )
    assert 1 < overlay.line_count <= 3
    assert 42 <= overlay.font_size <= 72
    assert overlay.safe_zone_ok
    assert overlay.box_x >= 108
    assert overlay.box_x + overlay.box_width <= 972
    assert review_text_layout(uuid4(), [overlay], 10).outcome == "PASS"


def test_realistic_cta_fits_two_lines_with_smaller_safe_font(tmp_path):
    hook = render_text_card(
        "Midnight strikes—watch the city defy gravity!",
        tmp_path / "hook.png", start_time=0.2, end_time=3.0, y=180,
    )
    cta = render_text_card(
        "Tap to share the gravity‑defying moment and follow for more sci‑fi spectacles!",
        tmp_path / "cta.png", start_time=7.3, end_time=9.8, y=1500,
        max_lines=2, initial_size=64, minimum_size=34,
    )
    assert cta.line_count == 2
    assert 34 <= cta.font_size <= 64
    assert cta.safe_zone_ok
    assert cta.box_x >= 108
    assert cta.box_x + cta.box_width <= 972
    assert review_text_layout(uuid4(), [hook, cta], 10).outcome == "PASS"


def test_layout_qa_fails_out_of_frame_overlay(tmp_path):
    overlay = render_text_card("Valid hook", tmp_path / "hook.png", start_time=0.2, end_time=3, y=180)
    broken = replace(overlay, box_x=-1, safe_zone_ok=False)
    review = review_text_layout(uuid4(), [broken], 10)
    assert review.outcome == "FAIL"
    assert "hook_in_frame" in review.diagnostics
