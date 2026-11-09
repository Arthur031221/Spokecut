"""One entry point for every export format, shared by the CLI and the server."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import ass, captions, export, render, timeline
from .project import EditState, Project

TEXT_FORMATS = {
    "srt": "text/plain",
    "vtt": "text/vtt",
    "ass": "text/plain",
    "edl": "text/plain",
    "fcpxml": "application/xml",
    "otio": "application/json",
    "json": "application/json",
}
FORMATS = ("mp4", *TEXT_FORMATS)


@dataclass
class Result:
    filename: str
    mime: str
    text: str | None = None
    path: Path | None = None


def _complement(keeps: list[tuple[float, float]], duration: float) -> list[tuple[float, float]]:
    cuts, pos = [], 0.0
    for start, end in keeps:
        if start - pos > 1e-6:
            cuts.append((pos, start))
        pos = end
    if duration - pos > 1e-6:
        cuts.append((pos, duration))
    return cuts


def caption_chunks(project: Project, segs) -> list[captions.Chunk]:
    media = project.media
    words = captions.kept_words(project, segs)
    return captions.chunk_words(words, project.language, ass.max_chars_for(media.width, media.height))


def export_project(
    project: Project,
    video: Path,
    fmt: str,
    state: EditState | None = None,
    out: Path | None = None,
    encoder: str = "auto",
    progress: Callable[[float], None] | None = None,
) -> Result:
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r}, expected one of {', '.join(FORMATS)}")
    if state is not None:
        project.state = state
    if out is not None and out.resolve() == video.resolve():
        raise ValueError("the output file is the source video, choose another name with -o")
    media = project.media
    keeps, segs = timeline.plan(project)
    stem = Path(media.file).stem
    suffix = ".spokecut"
    if fmt == "mp4":
        target = out or video.with_name(f"{stem}{suffix}.{'mp4' if media.has_video else 'm4a'}")
        burn = project.state.caption.get("burn", True) and media.has_video
        with tempfile.TemporaryDirectory(prefix="spokecut-ass-") as tmp:
            script = None
            if burn:
                script = Path(tmp) / "captions.ass"
                chunks = caption_chunks(project, segs)
                script.write_text(
                    ass.build_ass(chunks, media.width, media.height, project.state.caption), encoding="utf-8"
                )
            render.render(video, target, keeps, media.fps, media.has_video, script, encoder, progress)
        mime = "video/mp4" if media.has_video else "audio/mp4"
        return Result(target.name, mime, path=target)
    if fmt in ("srt", "vtt", "ass"):
        chunks = caption_chunks(project, segs)
        text = {
            "srt": lambda: captions.to_srt(chunks),
            "vtt": lambda: captions.to_vtt(chunks),
            "ass": lambda: ass.build_ass(chunks, media.width or 1920, media.height or 1080, project.state.caption),
        }[fmt]()
    elif fmt == "edl":
        text = export.to_edl(segs, media.fps, media.file, stem)
    elif fmt == "fcpxml":
        text = export.to_fcpxml(segs, media, video, stem)
    elif fmt == "otio":
        text = export.to_otio(segs, media, video, stem)
    else:
        cuts = _complement(keeps, media.duration)
        text = export.to_cutlist(segs, cuts, media, media.file)
    name = f"{stem}{suffix}.{fmt if fmt != 'json' else 'cuts.json'}"
    if out:
        out.write_text(text, encoding="utf-8")
    return Result(name, TEXT_FORMATS[fmt], text=text, path=out)
