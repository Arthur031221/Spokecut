"""Cut list exports: CMX3600 EDL, FCPXML, OpenTimelineIO JSON and a plain JSON cut list."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import quoteattr

from .timecode import exact_fps, hour_frames, is_drop_frame, rational, timecode, to_frames
from .timeline import Segment


def _clips(segs: list[Segment], fps: Fraction) -> list[tuple[int, int, int]]:
    """(source in, source out, record in) in frames."""
    out = []
    pos = 0
    for s in segs:
        a, b = to_frames(s.src_start, fps), to_frames(s.src_end, fps)
        out.append((a, b, pos))
        pos += b - a
    return out


def to_edl(segs: list[Segment], fps_value: float, clip_name: str, title: str = "Spokecut") -> str:
    fps = exact_fps(fps_value)
    start = hour_frames(fps)  # sequences conventionally start at 01:00:00:00
    lines = [f"TITLE: {title}", f"FCM: {'DROP FRAME' if is_drop_frame(fps) else 'NON-DROP FRAME'}", ""]
    for n, (a, b, rec) in enumerate(_clips(segs, fps), 1):
        length = b - a
        lines.append(
            f"{n:03d}  AX       B     C        {timecode(a, fps)} {timecode(b, fps)} "
            f"{timecode(start + rec, fps)} {timecode(start + rec + length, fps)}"
        )
        lines.append(f"* FROM CLIP NAME: {clip_name}")
        lines.append("")
    return "\n".join(lines)


def _format_name(width: int, height: int, fps: Fraction) -> str:
    rate = {Fraction(30000, 1001): "2997", Fraction(24000, 1001): "2398", Fraction(60000, 1001): "5994"}.get(
        fps, str(round(fps))
    )
    if height > width:
        return "FFVideoFormatRateUndefined"  # Final Cut has no named portrait formats
    return f"FFVideoFormat{height}p{rate}"


def to_fcpxml(segs: list[Segment], media, video_path: Path, name: str) -> str:
    fps = exact_fps(media.fps)
    frame_dur = rational(1, fps)
    total = to_frames(media.duration, fps)
    src = video_path.resolve().as_uri()
    seq_len = sum(to_frames(s.src_end, fps) - to_frames(s.src_start, fps) for s in segs)
    clips = []
    for a, b, rec in _clips(segs, fps):
        clips.append(
            f'            <asset-clip name={quoteattr(name)} ref="r2" offset="{rational(rec, fps)}" '
            f'start="{rational(a, fps)}" duration="{rational(b - a, fps)}" tcFormat="NDF"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n<fcpxml version="1.9">\n'
        "  <resources>\n"
        f'    <format id="r1" name="{_format_name(media.width, media.height, fps)}" frameDuration="{frame_dur}" '
        f'width="{media.width}" height="{media.height}"/>\n'
        f'    <asset id="r2" name={quoteattr(name)} start="0s" duration="{rational(total, fps)}" '
        f'hasVideo="1" hasAudio="1" format="r1" src="{src}"/>\n'
        '  </resources>\n  <library>\n    <event name="Spokecut">\n'
        f"      <project name={quoteattr(name + ' (Spokecut)')}>\n"
        f'        <sequence format="r1" duration="{rational(seq_len, fps)}" tcStart="0s" tcFormat="NDF">\n'
        "          <spine>\n" + "\n".join(clips) + "\n          </spine>\n        </sequence>\n      </project>\n"
        "    </event>\n  </library>\n</fcpxml>\n"
    )


def _rt(frames: int, rate: float) -> dict:
    return {"OTIO_SCHEMA": "RationalTime.1", "rate": rate, "value": frames}


def _tr(start: int, length: int, rate: float) -> dict:
    return {"OTIO_SCHEMA": "TimeRange.1", "start_time": _rt(start, rate), "duration": _rt(length, rate)}


def to_otio(segs: list[Segment], media, video_path: Path, name: str) -> str:
    fps = exact_fps(media.fps)
    rate = float(fps)
    ref = {
        "OTIO_SCHEMA": "ExternalReference.1",
        "target_url": video_path.resolve().as_uri(),
        "available_range": _tr(0, to_frames(media.duration, fps), rate),
        "metadata": {},
    }
    children = []
    for a, b, _ in _clips(segs, fps):
        children.append(
            {
                "OTIO_SCHEMA": "Clip.2",
                "name": name,
                "source_range": _tr(a, b - a, rate),
                "media_references": {"DEFAULT_MEDIA": ref},
                "active_media_reference_key": "DEFAULT_MEDIA",
                "metadata": {},
            }
        )
    track = {
        "OTIO_SCHEMA": "Track.1",
        "name": "Spokecut",
        "kind": "Video",
        "children": children,
        "metadata": {},
    }
    timeline = {
        "OTIO_SCHEMA": "Timeline.1",
        "name": name,
        "tracks": {"OTIO_SCHEMA": "Stack.1", "name": "tracks", "children": [track], "metadata": {}},
        "metadata": {"spokecut": {"source": video_path.name}},
    }
    return json.dumps(timeline, indent=2)


def to_cutlist(segs: list[Segment], cuts: list[tuple[float, float]], media, video_name: str) -> str:
    kept = sum(s.src_end - s.src_start for s in segs)
    doc = {
        "source": video_name,
        "fps": media.fps,
        "sourceDuration": round(media.duration, 3),
        "outputDuration": round(kept, 3),
        "removed": round(media.duration - kept, 3),
        "cuts": [{"start": round(s, 3), "end": round(e, 3)} for s, e in cuts],
        "keeps": [
            {
                "srcStart": round(s.src_start, 3),
                "srcEnd": round(s.src_end, 3),
                "outStart": round(s.out_start, 3),
                "outEnd": round(s.out_end, 3),
            }
            for s in segs
        ],
    }
    return json.dumps(doc, indent=2)
