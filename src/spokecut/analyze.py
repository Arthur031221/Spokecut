"""Video in, project out: probe, decode, transcribe, find quiet points and suggestions."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from . import audio, cleaner, snap, transcribe
from .project import EditState, Project, save_project, sidecar_path

Progress = Callable[[str, float], None]


def analyze(
    video: Path,
    model: str | None = None,
    language: str | None = None,
    device: str = "auto",
    verbatim: bool = False,
    progress: Progress | None = None,
    proxy_dir: Path | None = None,
) -> Project:
    say = progress or (lambda stage, fraction: None)
    say("probe", 0.0)
    media, codecs = audio.probe(video)
    say("decode", 0.0)
    samples = audio.decode_audio(video)
    model_name = model or transcribe.default_model(transcribe.has_cuda() if device == "auto" else device == "cuda")
    say("transcribe", 0.0)
    words, lang = transcribe.transcribe(samples, model_name, language, device, verbatim, lambda f: say("transcribe", f))
    say("snap", 0.0)
    energy = snap.energy_grid(samples)
    snaps = snap.snap_points(words, energy, media.duration)
    if audio.needs_proxy(video, codecs):
        say("proxy", 0.0)
        out = (proxy_dir or video.parent) / (video.stem + ".spokecut-proxy.mp4")
        audio.make_proxy(video, out, video=media.has_video)
        media.proxy = out.name
    project = Project(
        media=media,
        language=lang,
        model=transcribe.VERBATIM_MODEL if verbatim else model_name,
        words=words,
        snaps=snaps,
        suggestions=cleaner.suggestions(words, lang),
        peaks=audio.peaks(samples),
        state=EditState(),
    )
    sidecar = sidecar_path(video)
    if sidecar.is_file():
        # A new transcript has different word indices, so the old edit cannot carry over. Keep it.
        shutil.copy2(sidecar, sidecar.with_name(sidecar.name + ".bak"))
    save_project(project, sidecar)
    say("done", 1.0)
    return project
