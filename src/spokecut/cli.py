"""Command line entry point: edit (the default), transcribe, clean, export, doctor."""

from __future__ import annotations

import argparse
import secrets
import shutil
import sys
import webbrowser
from pathlib import Path

from . import __version__
from .exporting import FORMATS
from .project import CAPTION_STYLES

DEFAULT_PORT = 8765
COMMANDS = {"edit", "transcribe", "clean", "export", "doctor"}


def err(message: str = "", end: str = "\n") -> None:
    print(message, end=end, file=sys.stderr, flush=True)


def progress_printer():
    state = {"stage": ""}

    def report(stage: str, fraction: float) -> None:
        if stage != state["stage"] and state["stage"]:
            err()
        state["stage"] = stage
        err(f"\r{stage:<11}{fraction * 100:5.0f}%", end="")
        if stage == "done":
            err()

    return report


def seconds(text: str) -> float:
    value = float(text)
    if not 0 <= value <= 2:
        raise argparse.ArgumentTypeError("must be between 0 and 2 seconds")
    return value


def check_input(path: str):
    from .audio import MediaError, require_ffmpeg

    video = Path(path).expanduser()
    if not video.is_file():
        err(f"no such file: {video}")
        return None
    try:
        require_ffmpeg()
    except MediaError as exc:
        err(str(exc))
        return None
    return video


def project_for(args: argparse.Namespace, video: Path):
    """The sidecar when there is one, otherwise a fresh transcription."""
    from .analyze import analyze
    from .project import load_project, sidecar_path

    sidecar = sidecar_path(video)
    if sidecar.is_file() and not getattr(args, "retranscribe", False):
        return load_project(sidecar)
    return analyze(video, args.model, args.language, args.device, args.verbatim, progress_printer())


def cmd_edit(args: argparse.Namespace) -> int:
    import uvicorn

    from .server import Config, create_app

    if args.host in ("0.0.0.0", "::"):
        err("Bind to one address instead, for example --host 192.168.1.20. Spokecut can read and write your files.")
        return 2
    token = secrets.token_urlsafe(18)
    extra = frozenset({args.host} - {"127.0.0.1", "localhost"})
    app = create_app(Config(args.model, args.language, args.device, args.verbatim, token, extra))
    for name in args.files:
        video = check_input(name)
        if video is None:
            return 2
        app.state.open_video(video)
    shown = "localhost" if args.host == "127.0.0.1" else f"[{args.host}]" if ":" in args.host else args.host
    url = f"http://{shown}:{args.port}/?t={token}"
    print(f"Spokecut {__version__} is running. Open {url}")
    if not args.no_open:
        webbrowser.open(url)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_transcribe(args: argparse.Namespace) -> int:
    from .analyze import analyze
    from .project import sidecar_path

    video = check_input(args.file)
    if video is None:
        return 2
    project = analyze(video, args.model, args.language, args.device, args.verbatim, progress_printer())
    kinds = [h["kind"] for h in project.suggestions]
    print(
        f"{len(project.words)} words, language {project.language}, model {project.model}, "
        f"{kinds.count('filler')} fillers, {kinds.count('repeat')} repeats, saved {sidecar_path(video)}"
    )
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    from .cleaner import apply_cleanup
    from .exporting import export_project
    from .project import save_project, sidecar_path
    from .timeline import output_duration, plan

    video = check_input(args.file)
    if video is None:
        return 2
    project = project_for(args, video)
    state = apply_cleanup(project, args.fillers, args.repeats, args.loose, args.pauses)
    if args.keep is not None:
        state.pause["keep"] = args.keep
    if args.captions:
        state.caption["style"] = args.captions
    save_project(project, sidecar_path(video))
    # Whether to burn captions into this render is not part of the saved edit.
    state.caption["burn"] = bool(args.captions)
    keeps, _ = plan(project)
    before, after = project.media.duration, output_duration(keeps)
    out = Path(args.output) if args.output else None
    try:
        result = export_project(project, video, args.format, out=out, encoder=args.encoder, progress=_bar)
    except Exception as exc:
        err(f"\nexport failed: {exc}")
        return 1
    err()
    print(f"{before:.1f} s -> {after:.1f} s ({before - after:.1f} s removed), wrote {save(result, video)}")
    return 0


def save(result, video: Path) -> Path:
    """Where an export ended up. Text results are written beside the video, renders already are."""
    if result.path is not None:
        return result.path
    target = video.with_name(result.filename)
    target.write_text(result.text or "", encoding="utf-8")
    return target


def _bar(fraction: float) -> None:
    err(f"\rrender     {fraction * 100:5.0f}%", end="")


def cmd_export(args: argparse.Namespace) -> int:
    from .exporting import export_project
    from .project import load_project, sidecar_path

    video = check_input(args.file)
    if video is None:
        return 2
    sidecar = sidecar_path(video)
    if not sidecar.is_file():
        err(f"{sidecar.name} does not exist. Run `spokecut transcribe` or `spokecut edit` first.")
        return 2
    project = load_project(sidecar)
    out = Path(args.output) if args.output else None
    result = export_project(project, video, args.format, out=out, encoder=args.encoder, progress=_bar)
    err()
    print(f"wrote {save(result, video)}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from . import transcribe
    from .render import nvenc_works

    ok = True
    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        ok &= path is not None
        print(f"{tool:<9}{path or 'MISSING. Install ffmpeg: https://ffmpeg.org/download.html'}")
    cuda, why = transcribe.cuda_status()
    print(f"cuda     {'yes' if cuda else f'no, {why} (transcription runs on the CPU)'}")
    print(f"nvenc    {'yes' if shutil.which('ffmpeg') and nvenc_works() else 'no (rendering uses libx264)'}")
    print(f"model    {transcribe.default_model(cuda)}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spokecut", description="Edit talking video by editing its transcript.")
    parser.add_argument("--version", action="version", version=f"spokecut {__version__}")
    sub = parser.add_subparsers(dest="command")

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--model", help="Whisper model name or path (default: large-v3-turbo on a GPU, small on a CPU)")
        p.add_argument("--language", help="spoken language code, such as en or zh (default: detect)")
        p.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
        p.add_argument("--verbatim", action="store_true", help="use the CrisperWhisper model, which keeps um and uh")

    edit = sub.add_parser("edit", help="open the editor in your browser (default)")
    edit.add_argument("files", nargs="*", help="videos to open")
    edit.add_argument("--host", default="127.0.0.1")
    edit.add_argument("--port", type=int, default=DEFAULT_PORT)
    edit.add_argument("--no-open", action="store_true", help="do not open a browser window")
    common(edit)

    tr = sub.add_parser("transcribe", help="transcribe a video and write the project file next to it")
    tr.add_argument("file")
    common(tr)

    clean = sub.add_parser("clean", help="remove fillers, repeats and long pauses and write the result")
    clean.add_argument("file")
    clean.add_argument("-o", "--output")
    clean.add_argument("--format", choices=FORMATS, default="mp4")
    clean.add_argument("--pauses", type=float, metavar="SECONDS", help="shorten pauses at least this long")
    clean.add_argument(
        "--keep", type=seconds, metavar="SECONDS", help="silence left in a shortened pause (default 0.25)"
    )
    clean.add_argument("--no-fillers", dest="fillers", action="store_false")
    clean.add_argument("--no-repeats", dest="repeats", action="store_false")
    clean.add_argument("--loose", action="store_true", help="also cut phrases like 'you know'")
    clean.add_argument("--captions", choices=CAPTION_STYLES, help="burn in captions in this style")
    clean.add_argument("--encoder", choices=("auto", "nvenc", "x264"), default="auto")
    clean.add_argument("--retranscribe", action="store_true", help="ignore an existing project file")
    common(clean)

    export = sub.add_parser("export", help="export the saved edit of a video")
    export.add_argument("file")
    export.add_argument("--format", choices=FORMATS, required=True)
    export.add_argument("-o", "--output")
    export.add_argument("--encoder", choices=("auto", "nvenc", "x264"), default="auto")

    sub.add_parser("doctor", help="check ffmpeg, the GPU and the default model")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0] not in COMMANDS and not argv[0].startswith("-")):
        argv.insert(0, "edit")  # `spokecut talk.mp4` opens the editor
    elif argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--version"):
        argv.insert(0, "edit")
    args = build_parser().parse_args(argv)
    handler = {
        "edit": cmd_edit,
        "transcribe": cmd_transcribe,
        "clean": cmd_clean,
        "export": cmd_export,
        "doctor": cmd_doctor,
    }[args.command]
    try:
        return handler(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        from .audio import MediaError

        if isinstance(exc, MediaError | ValueError | OSError):
            err(f"\nspokecut: {exc}")
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
