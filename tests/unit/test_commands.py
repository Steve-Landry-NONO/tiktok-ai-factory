from pathlib import Path
from tiktok_factory.domain.models import StoryboardShot
from tiktok_factory.pipeline.renderer import FFmpegRenderer
from tiktok_factory.providers.local import SyntheticVideoProvider

def test_generator_command():
 c=SyntheticVideoProvider().command(StoryboardShot(number=1,concept='test',duration_seconds=1),Path('x.mp4'))
 assert '1080x1920' in ' '.join(c) and 'libx264' in c
def test_renderer_command():
 c=FFmpegRenderer().command([Path('a.mp4'),Path('b.mp4')],Path('x.mp4'),'hook')
 assert 'concat=n=2' in ' '.join(c) and '1080:1920' in ' '.join(c)
 assert '-an' in c


def test_renderer_audio_command_uses_aac_and_loudnorm():
 c=FFmpegRenderer().command([Path('a.mp4')],Path('x.mp4'),'hook',Path('audio.wav'))
 assert '-an' not in c
 assert c[c.index('-c:a') + 1] == 'aac'
 assert 'loudnorm=I=-16' in ' '.join(c)
