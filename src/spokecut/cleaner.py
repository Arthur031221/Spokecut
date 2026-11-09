"""Find disfluencies in a transcript: fillers, immediate repeats. Pauses live in timeline.find_pauses."""

from __future__ import annotations

import re
import unicodedata

# Sounds that are never real words. Safe to remove in bulk.
FILLERS: dict[str, set[str]] = {
    "en": {"um", "umm", "uh", "uhh", "uhm", "er", "err", "erm", "ah", "ahh", "hmm", "hm", "mm", "mmm", "mhm"},
    "es": {"eh", "ehh", "em", "mm", "mmm", "hmm", "ah", "ahh"},
    "fr": {"euh", "euhh", "heu", "hum", "hmm", "mm", "ben"},
    "de": {"äh", "ähm", "öh", "öhm", "hm", "hmm", "mhm", "mm"},
    "pt": {"hm", "hmm", "ahn", "ãhn", "eh", "ehh", "mm", "hum"},
    "ja": {
        "えーと",
        "えっと",
        "えーっと",
        "えー",
        "あのー",
        "あの",
        "あー",
        "うーん",
        "うん",
        "んー",
        "ええと",
    },
    "ko": {"음", "어", "으음", "에", "아", "흠"},
    "zh": {"呃", "嗯", "額", "额", "唔", "哦", "欸"},
}

# Phrases that are filler most of the time but also real words. Offered, never on by default.
LOOSE: dict[str, list[list[str]]] = {
    "en": [["you", "know"], ["i", "mean"], ["sort", "of"], ["kind", "of"], ["basically"], ["like"]],
    "es": [["o", "sea"], ["pues"], ["bueno"]],
    "fr": [["tu", "sais"], ["en", "fait"], ["du", "coup"]],
    "de": [["sozusagen"], ["quasi"], ["halt"]],
    "pt": [["tipo"], ["né"], ["então"]],
    "zh": [["那個"], ["然後"], ["就是"], ["那个"], ["然后"]],
}

# Languages written without spaces: Whisper returns multi-character chunks, so repeats are too risky.
NO_REPEAT = {"zh", "ja", "ko"}

VERBATIM_TAGS = {"um", "uh"}
_TAG = re.compile(r"\[(um|uh)\]", re.I)
_STRIP = re.compile(r"[^\w']+", re.UNICODE)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return _STRIP.sub("", text.replace("’", "'"))


def split_verbatim_tags(text: str) -> list[str]:
    """CrisperWhisper emits fillers as tags glued to punctuation, like ',[UH]the'. Split them out."""
    if "[" not in text:
        return [text]
    parts: list[str] = []
    pos = 0
    for m in _TAG.finditer(text):
        before = text[pos : m.start()].strip()
        if before and _STRIP.sub("", before):
            parts.append(before)
        parts.append(m.group(1).lower())
        pos = m.end()
    rest = text[pos:].strip()
    if rest and _STRIP.sub("", rest):
        parts.append(rest)
    return parts or [text]


def find_fillers(words, language: str, loose: bool = False) -> list[dict]:
    table = FILLERS.get(language, set()) | VERBATIM_TAGS
    hits = []
    for i, w in enumerate(words):
        if normalize(w.text) in table:
            hits.append({"kind": "filler", "words": [i], "text": w.text.strip(), "default": True})
    if loose:
        taken = {i for h in hits for i in h["words"]}
        for phrase in LOOSE.get(language, []):
            k = len(phrase)
            for i in range(len(words) - k + 1):
                span = list(range(i, i + k))
                if taken.isdisjoint(span) and [normalize(words[j].text) for j in span] == phrase:
                    hits.append(
                        {
                            "kind": "loose",
                            "words": span,
                            "text": " ".join(words[j].text.strip() for j in span),
                            "default": False,
                        }
                    )
                    taken.update(span)
    return sorted(hits, key=lambda h: h["words"][0])


def find_repeats(words, language: str, max_gap: float = 0.6) -> list[dict]:
    """A word said twice in a row. The first take is flagged, the last one is kept."""
    if language in NO_REPEAT:
        return []
    hits = []
    for i in range(len(words) - 1):
        a, b = normalize(words[i].text), normalize(words[i + 1].text)
        if a and a == b and not a.isdigit() and words[i + 1].start - words[i].end <= max_gap:
            hits.append({"kind": "repeat", "words": [i], "text": words[i].text.strip(), "default": True})
    return hits


def suggestions(words, language: str) -> list[dict]:
    hits = find_fillers(words, language, loose=True) + find_repeats(words, language)
    return sorted(hits, key=lambda h: h["words"][0])


def apply_cleanup(project, fillers: bool = True, repeats: bool = True, loose: bool = False, pause: float | None = None):
    """Mark suggestions and long pauses in the project's edit state. Returns the state."""
    from .timeline import find_pauses

    state = project.state
    wanted = {"filler": fillers, "repeat": repeats, "loose": loose}
    marked = set(state.deleted)
    for hit in project.suggestions:
        if wanted.get(hit["kind"]):
            marked.update(hit["words"])
    state.deleted = sorted(marked)
    if pause is not None:
        state.pause["threshold"] = pause
        state.cut_gaps = sorted(set(state.cut_gaps) | set(find_pauses(project.words, pause)))
    return state
