"""The project file: transcript, snap points and the edit state, stored beside the video."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

VERSION = 1
SIDECAR_SUFFIX = ".spokecut.json"

DEFAULT_PAUSE = {"threshold": 0.7, "keep": 0.25}
DEFAULT_CAPTION = {
    "style": "highlight",
    "position": "bottom",
    "size": 7.0,
    "color": "#FFFFFF",
    "accent": "#FFB224",
    "uppercase": False,
    "burn": True,
}


@dataclass
class Word:
    text: str
    start: float
    end: float
    prob: float = 1.0

    def to_json(self) -> dict:
        return {"t": self.text, "s": round(self.start, 3), "e": round(self.end, 3), "p": round(self.prob, 3)}

    @classmethod
    def from_json(cls, d: dict) -> Word:
        return cls(d["t"], float(d["s"]), float(d["e"]), float(d.get("p", 1.0)))


@dataclass
class EditState:
    """What the user decided. Word indices refer to Project.words."""

    deleted: list[int] = field(default_factory=list)
    cut_gaps: list[int] = field(default_factory=list)
    edits: dict[int, str] = field(default_factory=dict)
    pause: dict = field(default_factory=lambda: dict(DEFAULT_PAUSE))
    caption: dict = field(default_factory=lambda: dict(DEFAULT_CAPTION))

    def to_json(self) -> dict:
        return {
            "deleted": sorted(set(self.deleted)),
            "cutGaps": sorted(set(self.cut_gaps)),
            "edits": {str(k): v for k, v in sorted(self.edits.items())},
            "pause": self.pause,
            "caption": self.caption,
        }

    @classmethod
    def from_json(cls, d: dict | None) -> EditState:
        d = d or {}
        return cls(
            deleted=[int(i) for i in d.get("deleted", [])],
            cut_gaps=[int(i) for i in d.get("cutGaps", [])],
            edits={int(k): str(v) for k, v in d.get("edits", {}).items()},
            pause={**DEFAULT_PAUSE, **d.get("pause", {})},
            caption={**DEFAULT_CAPTION, **d.get("caption", {})},
        )


@dataclass
class Media:
    file: str
    duration: float
    fps: float
    width: int = 0
    height: int = 0
    has_video: bool = True
    proxy: str | None = None

    def to_json(self) -> dict:
        return {
            "file": self.file,
            "proxy": self.proxy,
            "duration": round(self.duration, 3),
            "fps": round(self.fps, 3),
            "width": self.width,
            "height": self.height,
            "hasVideo": self.has_video,
        }

    @classmethod
    def from_json(cls, d: dict) -> Media:
        return cls(
            d["file"],
            float(d["duration"]),
            float(d["fps"]),
            int(d.get("width", 0)),
            int(d.get("height", 0)),
            bool(d.get("hasVideo", True)),
            d.get("proxy"),
        )


@dataclass
class Project:
    media: Media
    language: str
    model: str
    words: list[Word]
    snaps: list[float]
    suggestions: list[dict] = field(default_factory=list)
    peaks: dict = field(default_factory=dict)
    state: EditState = field(default_factory=EditState)

    def to_json(self) -> dict:
        return {
            "version": VERSION,
            "media": self.media.to_json(),
            "language": self.language,
            "model": self.model,
            "words": [w.to_json() for w in self.words],
            "snaps": [round(s, 3) for s in self.snaps],
            "suggestions": self.suggestions,
            "peaks": self.peaks,
            "state": self.state.to_json(),
        }

    @classmethod
    def from_json(cls, d: dict) -> Project:
        if d.get("version") != VERSION:
            raise ValueError(f"unsupported project version {d.get('version')!r}")
        words = [Word.from_json(w) for w in d["words"]]
        snaps = [float(s) for s in d["snaps"]]
        if len(snaps) != len(words) + 1:
            raise ValueError("snaps must have one more entry than words")
        return cls(
            Media.from_json(d["media"]),
            d.get("language", "en"),
            d.get("model", ""),
            words,
            snaps,
            d.get("suggestions", []),
            d.get("peaks", {}),
            EditState.from_json(d.get("state")),
        )

    def word_text(self, i: int) -> str:
        return self.state.edits.get(i, self.words[i].text).strip()


def sidecar_path(video: Path) -> Path:
    return video.with_name(video.name + SIDECAR_SUFFIX)


def load_project(path: Path) -> Project:
    return Project.from_json(json.loads(Path(path).read_text(encoding="utf-8")))


def save_project(project: Project, path: Path) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(project.to_json(), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
CAPTION_STYLES = ("highlight", "karaoke", "pop", "lowerthird", "plain")
CAPTION_POSITIONS = ("bottom", "middle", "top")


def validate_state(data: object, n_words: int) -> EditState:
    """Parse an edit state sent by a client. Raises ValueError with a message the UI can show."""
    if not isinstance(data, dict):
        raise ValueError("state must be an object")

    def indices(key: str, name: str) -> list[int]:
        raw = data.get(key, [])
        if not isinstance(raw, list) or any(type(i) is not int or not 0 <= i < n_words for i in raw):
            raise ValueError(f"{name} must be a list of word indices between 0 and {n_words - 1}")
        return raw

    def number(source: dict, key: str, low: float, high: float) -> float:
        value = source.get(key)
        if type(value) not in (int, float) or not low <= value <= high:
            raise ValueError(f"{key} must be a number between {low} and {high}")
        return float(value)

    edits = data.get("edits", {})
    if not isinstance(edits, dict):
        raise ValueError("edits must be an object")
    parsed_edits: dict[int, str] = {}
    for key, text in edits.items():
        if not str(key).isdigit() or not 0 <= int(key) < n_words or not isinstance(text, str) or len(text) > 200:
            raise ValueError("edits must map word indices to short strings")
        parsed_edits[int(key)] = text

    state = EditState.from_json({"deleted": indices("deleted", "deleted"), "cutGaps": indices("cutGaps", "cutGaps")})
    state.edits = parsed_edits
    for key in ("pause", "caption"):
        if not isinstance(data.get(key) or {}, dict):
            raise ValueError(f"{key} must be an object")
    pause = {**DEFAULT_PAUSE, **(data.get("pause") or {})}
    state.pause = {"threshold": number(pause, "threshold", 0.1, 10), "keep": number(pause, "keep", 0.0, 2.0)}
    caption = {**DEFAULT_CAPTION, **(data.get("caption") or {})}
    if caption["style"] not in CAPTION_STYLES or caption["position"] not in CAPTION_POSITIONS:
        raise ValueError("unknown caption style or position")
    if not _COLOR.fullmatch(str(caption["color"])) or not _COLOR.fullmatch(str(caption["accent"])):
        raise ValueError("caption colours must look like #RRGGBB")
    state.caption = {
        "style": caption["style"],
        "position": caption["position"],
        "size": number(caption, "size", 2.0, 20.0),
        "color": caption["color"].upper(),
        "accent": caption["accent"].upper(),
        "uppercase": bool(caption["uppercase"]),
        "burn": bool(caption["burn"]),
    }
    return state
