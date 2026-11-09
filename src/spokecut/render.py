"""Render the edit with ffmpeg: frame-exact cuts, short fades at every join, optional burned captions."""

from __future__ import annotations

import functools
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from .audio import MediaError

FADE = 0.015  # seconds of fade on each side of a join


@functools.lru_cache(maxsize=1)
def nvenc_works() -> bool:
    """True when this machine can encode H.264 on the GPU. Checked once with a one frame encode."""
    if shutil.which("ffmpeg") is None:
        return False
    run = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=256x256:d=0.1",
            "-c:v",
            "h264_nvenc",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
    )
    return run.returncode == 0


def build_filter(
    keeps: list[tuple[float, float]], fps: float, has_video: bool, ass: Path | None = None, fade: float = FADE
) -> str:
    """The filter_complex script: one trim per kept range, concatenated."""
    n = len(keeps)
    lines = []
    if has_video:
        outs = "".join(f"[sv{i}]" for i in range(n))
        lines.append(f"[0:v]fps={fps:.6f},split={n}{outs}" if n > 1 else f"[0:v]fps={fps:.6f}[sv0]")
    outs = "".join(f"[sa{i}]" for i in range(n))
    lines.append(f"[0:a]asplit={n}{outs}" if n > 1 else "[0:a]anull[sa0]")
    for i, (s, e) in enumerate(keeps):
        if has_video:
            fs, fe = round(s * fps), round(e * fps)
            lines.append(f"[sv{i}]trim=start_frame={fs}:end_frame={fe},setpts=PTS-STARTPTS[tv{i}]")
        f = min(fade, (e - s) / 2)
        lines.append(
            f"[sa{i}]atrim=start={s:.6f}:end={e:.6f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={f:.4f},afade=t=out:st={e - s - f:.6f}:d={f:.4f}[ta{i}]"
        )
    if has_video:
        joined = "".join(f"[tv{i}][ta{i}]" for i in range(n))
        label = "[v0]" if ass else "[v]"
        lines.append(f"{joined}concat=n={n}:v=1:a=1{label}[a]")
        if ass:
            lines.append(f"[v0]ass={_filter_path(ass)}[v]")
    else:
        joined = "".join(f"[ta{i}]" for i in range(n))
        lines.append(f"{joined}concat=n={n}:v=0:a=1[a]")
    return ";\n".join(lines)


def _filter_path(path: Path) -> str:
    """Escape a path for use inside an ffmpeg filter argument."""
    text = str(path).replace("\\", "/")
    return "'" + re.sub(r"([:'\\])", r"\\\1", text) + "'"


def encoder_args(encoder: str) -> list[str]:
    if encoder == "auto":
        encoder = "nvenc" if nvenc_works() else "x264"
    if encoder == "nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "21", "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "19"]


def render(
    video: Path,
    out: Path,
    keeps: list[tuple[float, float]],
    fps: float,
    has_video: bool = True,
    ass: Path | None = None,
    encoder: str = "auto",
    progress: Callable[[float], None] | None = None,
) -> None:
    if not keeps:
        raise MediaError("nothing is left to render: every part of the media is cut")
    total = sum(e - s for s, e in keeps)
    with tempfile.TemporaryDirectory(prefix="spokecut-") as tmp:
        script = Path(tmp) / "graph.txt"
        script.write_text(build_filter(keeps, fps, has_video, ass), encoding="utf-8")
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-filter_complex_script", str(script)]
        if has_video:
            cmd += ["-map", "[v]", "-map", "[a]", *encoder_args(encoder), "-pix_fmt", "yuv420p"]
        else:
            cmd += ["-map", "[a]"]
        cmd += ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(out)]
        log = Path(tmp) / "ffmpeg.log"
        # stderr goes to a file so a chatty ffmpeg can never fill a pipe while we read the progress lines.
        with log.open("w") as log_file:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log_file, text=True)
            assert proc.stdout is not None
            for line in proc.stdout:
                if line.startswith("out_time_us=") and progress and total:
                    try:
                        progress(max(0.0, min(1.0, int(line.split("=")[1]) / 1e6 / total)))
                    except ValueError:
                        pass
            failed = proc.wait()
        if failed:
            raise MediaError(f"ffmpeg failed: {log.read_text(errors='replace').strip()[-400:]}")
