"""Group kept words into caption chunks and write SRT, VTT and ASS.

web/js/captions.js repeats the chunking for the live preview. Both are checked against
tests/golden/captions.json.
"""

from __future__ import annotations

from dataclasses import dataclass

from .timeline import Segment, to_output

SENTENCE_END = ("。", "！", "？", ".", "!", "?", "…")
CLAUSE_END = ("，", "、", ",", ";", ":", "；", "：")
NO_SPACE = {"zh", "ja", "ko"}


@dataclass
class CapWord:
    text: str
    start: float  # output seconds
    end: float


@dataclass
class Chunk:
    words: list[CapWord]
    sep: str

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end

    def text(self) -> str:
        return self.sep.join(w.text for w in self.words)


def kept_words(project, segs: list[Segment]) -> list[CapWord]:
    """Words that survive the edit, with start and end moved onto the output timeline."""
    deleted = set(project.state.deleted)
    out = []
    for i, w in enumerate(project.words):
        if i in deleted:
            continue
        mid = (w.start + w.end) / 2
        if to_output(segs, mid) is None:
            continue
        s = to_output(segs, max(w.start, _seg_start(segs, mid)))
        e = to_output(segs, min(w.end, _seg_end(segs, mid)))
        text = project.word_text(i)
        if text:
            out.append(CapWord(text, s, max(e, s + 0.04)))
    return out


def _seg_start(segs, t):
    return next(s.src_start for s in segs if s.src_start - 1e-6 <= t <= s.src_end + 1e-6)


def _seg_end(segs, t):
    return next(s.src_end for s in segs if s.src_start - 1e-6 <= t <= s.src_end + 1e-6)


def chunk_words(
    words: list[CapWord], language: str, max_chars: int = 32, max_words: int = 7, max_gap: float = 0.8
) -> list[Chunk]:
    sep = "" if language in NO_SPACE else " "
    chunks: list[Chunk] = []
    cur: list[CapWord] = []
    for w in words:
        if cur:
            length = len(sep.join(x.text for x in cur + [w]))
            gap = w.start - cur[-1].end
            full = len(cur) >= max_words or length > max_chars
            if gap > max_gap or full or cur[-1].text.endswith(SENTENCE_END):
                chunks.append(Chunk(cur, sep))
                cur = []
            elif cur[-1].text.endswith(CLAUSE_END) and length > max_chars * 0.6:
                chunks.append(Chunk(cur, sep))
                cur = []
        cur.append(w)
    if cur:
        chunks.append(Chunk(cur, sep))
    return chunks


def _ts(t: float, comma: bool) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{',' if comma else '.'}{ms:03d}"


def to_srt(chunks: list[Chunk]) -> str:
    rows = []
    for n, c in enumerate(chunks, 1):
        rows.append(f"{n}\n{_ts(c.start, True)} --> {_ts(c.end, True)}\n{c.text()}\n")
    return "\n".join(rows)


def to_vtt(chunks: list[Chunk]) -> str:
    rows = ["WEBVTT\n"]
    for c in chunks:
        rows.append(f"{_ts(c.start, False)} --> {_ts(c.end, False)}\n{c.text()}\n")
    return "\n".join(rows)
