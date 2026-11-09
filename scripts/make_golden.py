"""Write tests/golden/*.json from the Python implementation.

The browser preview in web/js repeats the timeline and caption arithmetic. tests/js checks it against these
files, and tests/test_golden.py checks that they match the Python code, so the two cannot drift apart.

    python scripts/make_golden.py          # rewrite the files
    python scripts/make_golden.py --check  # exit 1 if they are out of date
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from spokecut import captions, timeline
from spokecut.captions import CapWord
from spokecut.project import EditState, Media, Project, Word

GOLDEN = Path(__file__).resolve().parent.parent / "tests" / "golden"


def transcript(texts: list[str], pauses: dict[int, float], fps: float, language: str = "en") -> Project:
    words, t = [], 0.4
    for i, text in enumerate(texts):
        t += pauses.get(i, 0.0)
        words.append(Word(text, round(t, 3), round(t + 0.3, 3)))
        t += 0.4
    snaps = [0.0] + [round((a.end + b.start) / 2, 3) for a, b in zip(words, words[1:], strict=False)]
    duration = round(words[-1].end + 0.6, 3)
    snaps.append(duration)
    return Project(Media("a.mp4", duration, fps, 1280, 720, fps > 0), language, "golden", words, snaps)


TEXTS = "so um today we want to to talk about editing . most people cut video , but speech is text .".split()

TIMELINE_CASES = [
    ("nothing deleted", [], [], 0.25, 30.0),
    ("one word", [4], [], 0.25, 30.0),
    ("a run of words", [1, 2, 3], [], 0.25, 30.0),
    ("first word", [0], [], 0.25, 30.0),
    ("last word", [len(TEXTS) - 1], [], 0.25, 30.0),
    ("two runs", [1, 6, 7], [], 0.25, 30.0),
    ("pauses only", [], [8, 14], 0.25, 30.0),
    ("pause next to a deleted word", [8], [8, 9], 0.25, 30.0),
    ("short pause is kept", [], [3], 0.25, 30.0),
    ("drop frame rate", [2, 3], [8], 0.25, 29.97),
    ("24 fps", [5, 6], [14], 0.4, 24.0),
    ("audio only", [2, 3], [8], 0.25, 0.0),
    ("everything deleted", list(range(len(TEXTS))), [], 0.25, 30.0),
    ("edited and emptied words", [2], [8], 0.25, 30.0, {0: "Thus", 4: "  "}),
]


def timeline_golden() -> list[dict]:
    out = []
    for name, deleted, gaps, keep, fps, *rest in TIMELINE_CASES:
        edits = rest[0] if rest else {}
        p = transcript(TEXTS, {8: 1.2, 14: 1.0}, fps)
        p.state = EditState(deleted=deleted, cut_gaps=gaps, edits=edits, pause={"threshold": 0.7, "keep": keep})
        keeps, segs = timeline.plan(p)
        kept = captions.kept_words(p, segs)
        probes = [0.0, 0.5, 1.7, 3.3, 5.0, p.media.duration]
        out.append(
            {
                "name": name,
                "fps": fps,
                "duration": p.media.duration,
                "words": [[w.text, w.start, w.end] for w in p.words],
                "snaps": p.snaps,
                "deleted": deleted,
                "cutGaps": gaps,
                "edits": {str(k): v for k, v in edits.items()},
                "keep": keep,
                "keeps": [[round(s, 6), round(e, 6)] for s, e in keeps],
                "outputDuration": round(timeline.output_duration(keeps), 6),
                "kept": [[w.text, round(w.start, 6), round(w.end, 6)] for w in kept],
                "pauses": timeline.find_pauses(p.words, 0.7),
                "probes": [[t, None if (o := timeline.to_output(segs, t)) is None else round(o, 6)] for t in probes],
            }
        )
    return out


CAPTION_CASES = [
    (
        "short sentence",
        "en",
        [("Hello", 0, 0.4), ("there.", 0.5, 0.9), ("Next", 1.0, 1.3), ("one", 1.4, 1.6)],
        32,
        7,
        0.8,
    ),
    ("long gap", "en", [("a", 0, 0.3), ("b", 0.4, 0.7), ("c", 2.0, 2.3)], 32, 7, 0.8),
    ("word limit", "en", [(f"w{i}", i * 0.3, i * 0.3 + 0.2) for i in range(12)], 200, 5, 0.8),
    ("char limit", "en", [("abcdefgh", i * 0.3, i * 0.3 + 0.2) for i in range(7)], 20, 7, 0.8),
    (
        "clause break",
        "en",
        [("when", 0, 0.2), ("we", 0.3, 0.5), ("arrive,", 0.6, 0.9), ("we", 1.0, 1.2), ("eat", 1.3, 1.5)],
        12,
        7,
        0.8,
    ),
    ("chinese", "zh", [("你好", 0, 0.3), ("世界。", 0.4, 0.7), ("再見", 0.8, 1.1)], 16, 7, 0.8),
    ("japanese", "ja", [("こんにちは", 0, 0.5), ("世界", 0.6, 0.9)], 16, 7, 0.8),
]


def captions_golden() -> list[dict]:
    out = []
    for name, lang, items, max_chars, max_words, max_gap in CAPTION_CASES:
        chunks = captions.chunk_words([CapWord(*w) for w in items], lang, max_chars, max_words, max_gap)
        out.append(
            {
                "name": name,
                "language": lang,
                "words": [list(w) for w in items],
                "maxChars": max_chars,
                "maxWords": max_words,
                "maxGap": max_gap,
                "chunks": [[w.text for w in c.words] for c in chunks],
                "text": [c.text() for c in chunks],
            }
        )
    return out


def main() -> int:
    files = {"timeline.json": timeline_golden(), "captions.json": captions_golden()}
    stale = []
    for name, data in files.items():
        text = json.dumps(data, indent=1, ensure_ascii=True) + "\n"
        path = GOLDEN / name
        if "--check" in sys.argv:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            GOLDEN.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    if stale:
        print("out of date:", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
