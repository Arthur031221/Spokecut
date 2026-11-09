"""Edit state to cut ranges, kept ranges and the source to output time map.

web/js/timeline.js implements the same arithmetic for the live preview. Both are
checked against tests/golden/timeline.json.
"""

from __future__ import annotations

from dataclasses import dataclass

EPS = 1e-6


def pause_cut(prev_end: float, next_start: float, keep: float) -> tuple[float, float] | None:
    """The middle of a pause that leaves `keep` seconds of silence, or None if it is already short."""
    if next_start - prev_end <= keep + EPS:
        return None
    half = keep / 2
    return (prev_end + half, next_start - half)


def find_pauses(words, threshold: float) -> list[int]:
    """Gap indices g (between word g-1 and word g) whose silence is at least `threshold` seconds."""
    return [g for g in range(1, len(words)) if words[g].start - words[g - 1].end >= threshold - EPS]


def merge(ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for s, e in sorted(ranges):
        if e - s <= EPS:
            continue
        if out and s <= out[-1][1] + EPS:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def cut_ranges(words, snaps, deleted, cut_gaps, keep: float, duration: float) -> list[tuple[float, float]]:
    """Time ranges to remove, in source seconds.

    A run of deleted words i..j is cut from the quiet point before word i to the quiet point after
    word j, so no half a word is left behind. A run touching the first or last word cuts to the
    start or end of the media. A cut gap removes the middle of that pause.
    """
    n = len(words)
    ranges: list[tuple[float, float]] = []
    marked = sorted({i for i in deleted if 0 <= i < n})
    i = 0
    while i < len(marked):
        j = i
        while j + 1 < len(marked) and marked[j + 1] == marked[j] + 1:
            j += 1
        first, last = marked[i], marked[j]
        start = 0.0 if first == 0 else snaps[first]
        end = duration if last == n - 1 else snaps[last + 1]
        ranges.append((start, end))
        i = j + 1
    for g in sorted(set(cut_gaps)):
        if 1 <= g < n:
            cut = pause_cut(words[g - 1].end, words[g].start, keep)
            if cut:
                ranges.append(cut)
    return merge([(max(0.0, s), min(duration, e)) for s, e in ranges])


def snap_to_frames(ranges: list[tuple[float, float]], fps: float) -> list[tuple[float, float]]:
    """Round range edges to the nearest frame and drop ranges shorter than a frame."""
    if fps <= 0:
        return ranges
    out = []
    for s, e in ranges:
        fs, fe = round(s * fps), round(e * fps)
        if fe > fs:
            out.append((fs / fps, fe / fps))
    return merge(out)


def keep_ranges(cuts: list[tuple[float, float]], duration: float, fps: float = 0.0) -> list[tuple[float, float]]:
    """The complement of the cuts inside [0, duration]."""
    keeps: list[tuple[float, float]] = []
    pos = 0.0
    for s, e in cuts:
        if s - pos > EPS:
            keeps.append((pos, s))
        pos = max(pos, e)
    if duration - pos > EPS:
        keeps.append((pos, duration))
    if fps > 0:
        keeps = [(s, e) for s, e in keeps if round(e * fps) > round(s * fps)]
    return keeps


@dataclass(frozen=True)
class Segment:
    src_start: float
    src_end: float
    out_start: float

    @property
    def out_end(self) -> float:
        return self.out_start + (self.src_end - self.src_start)


def segments(keeps: list[tuple[float, float]]) -> list[Segment]:
    out, pos = [], 0.0
    for s, e in keeps:
        out.append(Segment(s, e, pos))
        pos += e - s
    return out


def output_duration(keeps: list[tuple[float, float]]) -> float:
    return sum(e - s for s, e in keeps)


def to_output(segs: list[Segment], t: float) -> float | None:
    """Output time of source time `t`, or None when `t` was cut."""
    for seg in segs:
        if seg.src_start - EPS <= t <= seg.src_end + EPS:
            return seg.out_start + (min(max(t, seg.src_start), seg.src_end) - seg.src_start)
    return None


def plan(project, state=None) -> tuple[list[tuple[float, float]], list[Segment]]:
    """Frame-snapped keep ranges and segments for a project and edit state."""
    state = state or project.state
    media = project.media
    fps = media.fps if media.has_video else 0.0
    cuts = cut_ranges(
        project.words,
        project.snaps,
        state.deleted,
        state.cut_gaps,
        float(state.pause["keep"]),
        media.duration,
    )
    cuts = snap_to_frames(cuts, fps)
    keeps = keep_ranges(cuts, media.duration, fps)
    return keeps, segments(keeps)
