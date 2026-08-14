import subprocess

from tiktok_factory.domain.models import StoryboardShot
from tiktok_factory.pipeline.renderer import FFmpegRenderer, probe
from tiktok_factory.providers.local import SyntheticVideoProvider, require_tool


def video_stream(data):
    return next(stream for stream in data["streams"] if stream["codec_type"] == "video")


def test_render_without_audio(tmp_path):
    clip = SyntheticVideoProvider().generate(
        StoryboardShot(number=1, concept="silent", duration_seconds=0.3), tmp_path / "clip.mp4"
    )
    final = FFmpegRenderer().render([clip], tmp_path / "silent.mp4", "Silent hook")
    data = probe(final)
    video = video_stream(data)
    assert video["codec_name"] == "h264"
    assert (video["width"], video["height"]) == (1080, 1920)
    assert abs(eval_fraction(video["avg_frame_rate"]) - 30) < 0.1
    assert not any(stream["codec_type"] == "audio" for stream in data["streams"])


def test_render_with_normalized_aac_audio(tmp_path):
    require_tool("ffmpeg")
    clip = SyntheticVideoProvider().generate(
        StoryboardShot(number=1, concept="audio", duration_seconds=0.5), tmp_path / "clip.mp4"
    )
    audio = tmp_path / "tone.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5", str(audio)
    ], check=True, capture_output=True)
    final = FFmpegRenderer().render([clip], tmp_path / "audio.mp4", "Audio hook", audio)
    data = probe(final)
    video = video_stream(data)
    audio_stream = next(stream for stream in data["streams"] if stream["codec_type"] == "audio")
    assert video["codec_name"] == "h264"
    assert (video["width"], video["height"]) == (1080, 1920)
    assert abs(eval_fraction(video["avg_frame_rate"]) - 30) < 0.1
    assert audio_stream["codec_name"] == "aac"
    assert float(data["format"]["duration"]) > 0


def eval_fraction(value: str) -> float:
    numerator, denominator = value.split("/")
    return float(numerator) / float(denominator)
