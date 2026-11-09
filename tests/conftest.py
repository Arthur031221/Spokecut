from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from spokecut.project import Media, Project, Word

SAMPLE = (
    "So um today I want to to talk about editing . "
    "Most people cut video on a timeline , but speech is text . "
    "If you can read it you can edit it ."
).split()


def make_project(fps: float = 30.0, duration: float = 20.0, language: str = "en", has_video: bool = True) -> Project:
    """A deterministic transcript: 0.3 s words with a 0.1 s gap, and two long pauses."""
    words, t = [], 0.4
    for i, text in enumerate(SAMPLE):
        if i in (9, 17):
            t += 1.0
        words.append(Word(text, round(t, 3), round(t + 0.3, 3)))
        t += 0.4
    snaps = [0.0]
    for a, b in zip(words, words[1:], strict=False):
        snaps.append(round((a.end + b.start) / 2, 3))
    snaps.append(duration)
    media = Media("talk.mp4", duration, fps, 1280, 720, has_video)
    return Project(media, language, "test", words, snaps)


@pytest.fixture
def project() -> Project:
    return make_project()


needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not installed")


@pytest.fixture(scope="session")
def tone_video(tmp_path_factory) -> Path:
    """Three seconds of test pattern with a 440 Hz tone, 30 fps."""
    out = tmp_path_factory.mktemp("media") / "tone.mp4"
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is not installed")
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=3",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out),
        ],
        check=True,
    )  # fmt: skip
    return out
