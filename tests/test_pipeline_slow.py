"""The real thing: Whisper weights, ffmpeg and the demo clip, with nothing mocked."""

import shutil
from pathlib import Path

import pytest

from spokecut import analyze, cleaner, exporting, timeline
from spokecut.audio import probe
from spokecut.project import load_project, sidecar_path

CLIP = Path(__file__).resolve().parent.parent / "web" / "demo" / "clip.mp4"

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def analysed(tmp_path_factory):
    work = tmp_path_factory.mktemp("slow") / "clip.mp4"
    shutil.copy(CLIP, work)
    try:
        project = analyze.analyze(work, model="tiny.en", language="en", device="cpu")
    except Exception as err:  # weights are not cached and there is no network
        pytest.skip(f"tiny.en is not available: {err}")
    return work, project


def test_words_are_ordered_and_inside_the_clip(analysed):
    _, project = analysed
    words = project.words
    assert len(words) > 150
    assert all(a.start <= b.start for a, b in zip(words, words[1:], strict=False))
    assert words[-1].end <= project.media.duration + 0.01


def test_sidecar_round_trips(analysed):
    work, project = analysed
    again = load_project(sidecar_path(work))
    assert [w.text for w in again.words] == [w.text for w in project.words]


def test_cleaning_shortens_the_clip_and_the_mp4_matches(analysed, tmp_path):
    work, project = analysed
    cleaner.apply_cleanup(project, pause=0.7)
    keeps, _ = timeline.plan(project)
    expected = sum(e - s for s, e in keeps)
    assert expected < project.media.duration - 2
    out = tmp_path / "out.mp4"
    exporting.export_project(project, work, "mp4", out=out, encoder="x264")
    media, _ = probe(out)
    assert media.duration == pytest.approx(expected, abs=0.2)
