import json
from pathlib import Path

import opentimelineio as otio
import pytest
from conftest import make_project

from spokecut import timeline as tl
from spokecut.exporting import FORMATS, export_project
from spokecut.project import EditState

VIDEO = Path("/media/talk.mp4")


def planned(fps=30.0, **state):
    p = make_project(fps=fps)
    p.state = EditState(**state)
    keeps, segs = tl.plan(p)
    return p, keeps, segs


def frames(rt):
    return round(rt.value)


@pytest.mark.parametrize("fps", [24.0, 25.0, 30.0, 29.97, 59.94])
def test_otio_reads_back_with_the_same_cuts(fps, tmp_path):
    p, keeps, segs = planned(fps, deleted=[1, 2, 6], cut_gaps=[9])
    path = tmp_path / "t.otio"
    path.write_text(export_project(p, VIDEO, "otio").text)
    timeline = otio.adapters.read_from_file(str(path))
    clips = list(timeline.find_clips())
    assert len(clips) == len(segs)
    rate = clips[0].source_range.start_time.rate
    for clip, (start, end) in zip(clips, keeps, strict=True):
        assert clip.source_range.start_time.to_seconds() == pytest.approx(start, abs=0.6 / rate)
        assert clip.source_range.duration.to_seconds() == pytest.approx(end - start, abs=1.1 / rate)
    total = sum(c.source_range.duration.to_seconds() for c in clips)
    assert total == pytest.approx(tl.output_duration(keeps), abs=len(clips) / rate)


def test_otio_references_the_media_file():
    p, _, _ = planned(deleted=[3])
    doc = json.loads(export_project(p, VIDEO, "otio").text)
    ref = doc["tracks"]["children"][0]["children"][0]["media_references"]["DEFAULT_MEDIA"]
    assert ref["target_url"] == "file:///media/talk.mp4"


def test_edl_reads_back_through_the_cmx3600_adapter(tmp_path):
    p, keeps, segs = planned(deleted=[1, 2, 6], cut_gaps=[9])
    path = tmp_path / "t.edl"
    path.write_text(export_project(p, VIDEO, "edl").text)
    timeline = otio.adapters.read_from_file(str(path), rate=30)
    assert [t.kind for t in timeline.tracks] == ["Video", "Audio"]  # every event is picture and sound
    clips = list(timeline.video_tracks()[0].find_clips())
    assert len(clips) == len(segs)
    assert len(list(timeline.audio_tracks()[0].find_clips())) == len(segs)
    for clip, seg in zip(clips, segs, strict=True):
        assert clip.source_range.start_time.to_seconds() == pytest.approx(seg.src_start, abs=1 / 30)
        assert clip.source_range.duration.to_seconds() == pytest.approx(seg.src_end - seg.src_start, abs=1 / 30)


def test_edl_events_are_contiguous_on_the_record_side():
    p, _, _ = planned(deleted=[1, 2, 6])
    lines = [ln.split() for ln in export_project(p, VIDEO, "edl").text.splitlines() if ln[:3].isdigit()]
    for prev, cur in zip(lines, lines[1:], strict=False):
        assert prev[-1] == cur[-2]
    assert lines[0][-2].startswith("01:00:00")


def test_edl_uses_drop_frame_for_2997():
    p, _, _ = planned(29.97, deleted=[1])
    text = export_project(p, VIDEO, "edl").text
    assert "FCM: DROP FRAME" in text
    assert ";" in text.splitlines()[3]


def test_fcpxml_reads_back_through_the_fcpx_adapter(tmp_path):
    p, keeps, segs = planned(deleted=[1, 2, 6], cut_gaps=[9])
    path = tmp_path / "t.fcpxml"
    path.write_text(export_project(p, VIDEO, "fcpxml").text)
    timeline = otio.adapters.read_from_file(str(path), adapter_name="fcpx_xml")
    clips = list(timeline.find_clips())
    assert len(clips) == len(segs)
    total = sum(c.source_range.duration.to_seconds() for c in clips)
    assert total == pytest.approx(tl.output_duration(keeps), abs=0.05)


def test_fcpxml_names_a_portrait_frame_without_a_fake_final_cut_format():
    p, _, _ = planned(deleted=[1])
    p.media.width, p.media.height = 1080, 1920
    text = export_project(p, VIDEO, "fcpxml").text
    assert 'name="FFVideoFormatRateUndefined"' in text and 'width="1080" height="1920"' in text
    p.media.width, p.media.height = 1920, 1080
    assert "FFVideoFormat1080p" in export_project(p, VIDEO, "fcpxml").text


def test_fcpxml_escapes_names():
    p, _, _ = planned(deleted=[1])
    p.media.file = 'a "b" & <c>.mp4'
    text = export_project(p, Path('/m/a "b" & <c>.mp4'), "fcpxml").text
    import xml.etree.ElementTree as ET

    ET.fromstring(text.split("\n", 2)[2])  # must be well formed once the doctype line is gone


def test_cutlist_adds_up():
    p, keeps, _ = planned(deleted=[1, 2, 6], cut_gaps=[9])
    doc = json.loads(export_project(p, VIDEO, "json").text)
    assert doc["outputDuration"] + doc["removed"] == pytest.approx(doc["sourceDuration"], abs=0.002)
    assert len(doc["keeps"]) == len(keeps)
    assert len(doc["cuts"]) in (len(keeps) - 1, len(keeps), len(keeps) + 1)


def test_cutlist_cuts_do_not_overlap_keeps():
    p, keeps, _ = planned(deleted=[0, 1, 5])
    doc = json.loads(export_project(p, VIDEO, "json").text)
    for cut in doc["cuts"]:
        for s, e in keeps:
            assert cut["end"] <= s + 1e-3 or cut["start"] >= e - 1e-3


def test_srt_reflects_the_edit():
    p, _, _ = planned(deleted=[1])
    text = export_project(p, VIDEO, "srt").text
    assert " um " not in text.lower()
    assert text.startswith("1\n00:00:")


def test_every_text_format_has_a_filename_and_a_mime():
    p, _, _ = planned(deleted=[1])
    for fmt in FORMATS:
        if fmt == "mp4":
            continue
        r = export_project(p, VIDEO, fmt)
        assert r.filename.startswith("talk.spokecut.") and r.mime and r.text


def test_unknown_format_is_rejected():
    p, _, _ = planned()
    with pytest.raises(ValueError, match="unknown format"):
        export_project(p, VIDEO, "doc")
