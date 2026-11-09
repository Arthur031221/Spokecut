"""Burned-in caption styles as an ASS script for libass."""

from __future__ import annotations

from .captions import Chunk
from .project import CAPTION_STYLES

STYLES = CAPTION_STYLES
FONT = "Arial"


def ass_color(hex_rgb: str, alpha: int = 0) -> str:
    h = hex_rgb.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"expected #RRGGBB, got {hex_rgb!r}")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ts(t: float) -> str:
    cs = round(t * 100)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(text: str, upper: bool) -> str:
    text = text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")
    return text.upper() if upper else text


def max_chars_for(width: int, height: int) -> int:
    return 20 if height > width else 34


def build_ass(chunks: list[Chunk], width: int, height: int, caption: dict) -> str:
    style = caption.get("style", "highlight")
    if style not in STYLES:
        raise ValueError(f"unknown caption style {style!r}")
    size = round(height * float(caption.get("size", 7.0)) / 100)
    base = ass_color(caption.get("color", "#FFFFFF"))
    accent = ass_color(caption.get("accent", "#FFB224"))
    upper = bool(caption.get("uppercase"))
    align, margin_v = {
        "bottom": (2, round(height * 0.08)),
        "middle": (5, 0),
        "top": (8, round(height * 0.08)),
    }.get(caption.get("position", "bottom"), (2, round(height * 0.08)))
    border, outline, back = 1, max(2, round(size / 14)), ass_color("#000000", 0x80)
    edge = ass_color("#000000")
    margin_l = margin_r = round(width * 0.06)
    if style == "lowerthird":
        # With BorderStyle 3 libass paints the box in the outline colour.
        border, align, size = 3, 1, round(size * 0.8)
        outline = round(size * 0.3)
        edge = ass_color("#101114", 0x30)
        margin_v = round(height * 0.07)
        margin_l = round(width * 0.05)
    sec = base if style == "karaoke" else accent
    prim = accent if style == "karaoke" else base
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,"
        "Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Default,{FONT},{size},{prim},{sec},{edge},{back},-1,0,0,0,100,100,0,0,"
        f"{border},{outline},0,{align},{margin_l},{margin_r},{margin_v},1\n\n"
        "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )
    rows = []
    for chunk in chunks:
        rows.extend(_events(chunk, style, base, accent, upper))
    return header + "\n".join(f"Dialogue: 0,{_ts(s)},{_ts(e)},Default,,0,0,0,,{t}" for s, e, t in rows) + "\n"


def _events(chunk: Chunk, style: str, base: str, accent: str, upper: bool) -> list[tuple[float, float, str]]:
    words, sep = chunk.words, chunk.sep
    texts = [_esc(w.text, upper) for w in words]
    if style in ("plain", "lowerthird"):
        return [(chunk.start, chunk.end, sep.join(texts))]
    if style == "karaoke":
        parts = []
        for k, w in enumerate(words):
            nxt = words[k + 1].start if k + 1 < len(words) else w.end
            parts.append(f"{{\\kf{max(1, round((nxt - w.start) * 100))}}}{texts[k]}")
        return [(chunk.start, chunk.end, sep.join(parts))]
    events = []
    for k, w in enumerate(words):
        end = words[k + 1].start if k + 1 < len(words) else w.end
        if style == "highlight":
            parts = [f"{{\\c{accent}}}{t}{{\\c{base}}}" if j == k else t for j, t in enumerate(texts)]
            events.append((w.start, end, sep.join(parts)))
        else:  # pop: words appear one by one, the newest one bounces in
            shown = texts[:k] + [
                f"{{\\fscx60\\fscy60\\t(0,110,\\fscx115\\fscy115)\\t(110,200,\\fscx100\\fscy100)}}{texts[k]}"
            ]
            events.append((w.start, end, sep.join(shown)))
    return events
