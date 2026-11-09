import json
import re
import subprocess

import pytest
from conftest import needs_ffmpeg

from spokecut import render, timeline
from spokecut.audio import MediaError, probe

pytestmark = needs_ffmpeg


def duration(path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def test_filter_graph_has_a_trim_and_a_fade_per_keep():
    graph = render.build_filter([(0.0, 1.0), (2.0, 3.0)], 30.0, True, None)
    assert len(re.findall(r"(?<!a)trim=", graph)) == 2 and graph.count("atrim=") == 2
    assert graph.count("afade") >= 2 and "concat=n=2" in graph


def test_filter_graph_burns_captions_when_given(tmp_path):
    ass = tmp_path / "c.ass"
    ass.write_text("x")
    assert "ass=" in render.build_filter([(0.0, 1.0)], 30.0, True, ass)


def test_audio_only_graph_has_no_video_chain():
    assert not re.search(r"(?<!a)trim=", render.build_filter([(0.0, 1.0)], 0.0, False, None))


@pytest.mark.parametrize("encoder", ["x264"])
def test_render_matches_the_planned_duration(tone_video, tmp_path, encoder):
    keeps = [(0.0, 0.5), (1.0, 1.5), (2.0, 3.0)]
    out = tmp_path / "out.mp4"
    render.render(tone_video, out, keeps, 30.0, True, None, encoder)
    assert duration(out) == pytest.approx(timeline.output_duration(keeps), abs=0.1)
    media, _ = probe(out)
    assert (media.width, media.height) == (320, 240) and media.has_video


def test_render_reports_progress(tone_video, tmp_path):
    seen = []
    render.render(tone_video, tmp_path / "o.mp4", [(0.0, 2.0)], 30.0, True, None, "x264", seen.append)
    assert seen and seen[-1] == pytest.approx(1.0, abs=0.05)


def test_render_with_nothing_left_is_an_error(tone_video, tmp_path):
    with pytest.raises(MediaError, match="nothing is left"):
        render.render(tone_video, tmp_path / "o.mp4", [], 30.0)


def test_audio_only_render(tone_video, tmp_path):
    out = tmp_path / "o.m4a"
    render.render(tone_video, out, [(0.0, 1.0), (2.0, 3.0)], 0.0, False)
    assert duration(out) == pytest.approx(2.0, abs=0.1)
