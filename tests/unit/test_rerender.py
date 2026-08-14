import json
from pathlib import Path

import pytest

from tiktok_factory.pipeline.rerender import (
    ExistingClipsRerenderer,
    discover_clips,
    plan_narration_tempo,
)


class FakeTTS:
    def __init__(self):
        self.text = ""

    def synthesize(self, text: str, destination: Path) -> Path:
        self.text = text
        destination.write_bytes(b"fake wav")
        return destination


class FakeRenderer:
    def __init__(self):
        self.clips: list[Path] = []
        self.audio_tempo = 0.0
        self.target_duration = 0.0

    def render(
        self, clips, destination, hook="", audio_path=None, normalize_audio=True, overlays=None,
        audio_tempo=1.0, target_duration=None,
    ):
        self.clips = clips
        self.audio_tempo = audio_tempo
        self.target_duration = target_duration
        assert hook == ""
        assert audio_path.name == "narration.wav"
        assert overlays[0].safe_zone_ok
        destination.write_bytes(b"fake mp4")
        return destination


def test_rerender_uses_local_clips_and_fake_tts(tmp_path):
    clips = tmp_path / "artifact" / "nested"
    clips.mkdir(parents=True)
    (clips / "shot_2.mp4").write_bytes(b"two")
    (clips / "shot_1.mp4").write_bytes(b"one")
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({
        "script": {
            "hook": "Stop scrolling",
            "narration": "This is the story.",
            "call_to_action": "Follow.",
        },
        "assets": [
            {"storage_key": "output/runway_live/clips/attempt_1/shot_1.mp4"},
            {"storage_key": "output/runway_live/clips/attempt_1/shot_2.mp4"},
        ],
    }))
    tts, renderer = FakeTTS(), FakeRenderer()
    result = ExistingClipsRerenderer(
        tts, renderer,
        probe_fn=lambda _: {
            "format": {"duration": "2.0"},
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920,
                 "avg_frame_rate": "30/1", "display_aspect_ratio": "9:16", "duration": "2.0"},
                {"codec_type": "audio", "codec_name": "aac", "duration": "2.0"},
            ],
        },
        audio_duration_fn=lambda _: 4.1,
    ).run(tmp_path / "artifact", metadata, tmp_path / "output")
    assert [path.name for path in renderer.clips] == ["shot_1.mp4", "shot_2.mp4"]
    assert tts.text == "Stop scrolling This is the story. Follow."
    assert renderer.audio_tempo == pytest.approx(4.1 / 3.65)
    assert renderer.target_duration == pytest.approx(4.0)
    assert result.video.read_bytes() == b"fake mp4"
    manifest = json.loads(result.metadata.read_text())
    assert manifest["physical_clips"][0].endswith("shot_1.mp4")
    assert manifest["runway_calls"] == 0
    assert manifest["audio_tempo"] == pytest.approx(4.1 / 3.65, rel=1e-5)
    assert manifest["qa_text"]["outcome"] == "PASS"
    assert manifest["qa_audio"]["outcome"] == "PASS"


def test_plan_narration_tempo_matches_live_orpheus_case():
    tempo = plan_narration_tempo(21.590, 20.166668)
    assert tempo == pytest.approx(21.590 / (20.166668 - 0.35))
    assert 1.08 < tempo < 1.10


def test_plan_narration_tempo_does_not_slow_short_audio():
    assert plan_narration_tempo(15.0, 20.0) == 1.0


def test_plan_narration_tempo_rejects_unreasonable_speedup():
    with pytest.raises(ValueError, match="narration is too long"):
        plan_narration_tempo(30.0, 20.0)


def test_discover_clips_does_not_treat_storage_key_as_remote_storage(tmp_path):
    tmp_path.joinpath("shot_1.mp4").write_bytes(b"one")
    found = discover_clips(tmp_path, {"assets": [{"storage_key": "/gone/shot_1.mp4"}]})
    assert found == [tmp_path / "shot_1.mp4"]


def test_rerender_rejects_directory_without_physical_clips(tmp_path):
    with pytest.raises(ValueError, match="no MP4 clips"):
        discover_clips(tmp_path, {"assets": [{"storage_key": "shot_1.mp4"}]})
