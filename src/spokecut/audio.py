"""ffmpeg and ffprobe helpers: probe, decode, waveform peaks and the browser proxy."""

from __future__ import annotations

import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np

from .project import Media
from .snap import SAMPLE_RATE

BROWSER_VIDEO = {"h264", "vp8", "vp9", "av1"}
BROWSER_AUDIO = {"aac", "mp3", "opus", "vorbis", "flac", "pcm_s16le"}
BROWSER_CONTAINERS = {".mp4", ".m4v", ".mov", ".webm", ".m4a", ".mp3", ".wav", ".ogg", ".opus"}


class MediaError(RuntimeError):
    pass


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise MediaError(f"{tool} was not found on PATH. Install ffmpeg first (https://ffmpeg.org/download.html).")


def _probe_raw(path: Path) -> dict:
    require_ffmpeg()
    run = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    if run.returncode:
        raise MediaError(f"ffprobe could not read {path.name}: {run.stderr.strip()[:200]}")
    return json.loads(run.stdout)


def _rate(text: str) -> float:
    try:
        r = Fraction(text)
    except (ValueError, ZeroDivisionError):
        return 0.0
    return float(r)


def probe(path: Path) -> tuple[Media, dict]:
    """Media facts plus the codec names the proxy decision needs."""
    info = _probe_raw(path)
    streams = info.get("streams", [])
    video = next(
        (s for s in streams if s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic") != 1),
        None,
    )
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if audio is None:
        raise MediaError(f"{path.name} has no audio track to transcribe")
    duration = float(info.get("format", {}).get("duration") or (video or audio).get("duration") or 0)
    if duration <= 0:
        raise MediaError(f"{path.name} has no readable duration")
    fps = _rate(video.get("avg_frame_rate", "0")) or _rate(video.get("r_frame_rate", "0")) if video else 0.0
    media = Media(
        file=path.name,
        duration=duration,
        fps=fps or (30.0 if video else 0.0),
        width=int(video.get("width", 0)) if video else 0,
        height=int(video.get("height", 0)) if video else 0,
        has_video=video is not None,
    )
    codecs = {"video": video.get("codec_name") if video else None, "audio": audio.get("codec_name")}
    return media, codecs


def needs_proxy(path: Path, codecs: dict) -> bool:
    if path.suffix.lower() not in BROWSER_CONTAINERS:
        return True
    if codecs["video"] and codecs["video"] not in BROWSER_VIDEO:
        return True
    return codecs["audio"] not in BROWSER_AUDIO


def decode_audio(path: Path, rate: int = SAMPLE_RATE) -> np.ndarray:
    """The first audio track as mono float32 at `rate`."""
    run = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"],
        capture_output=True,
    )
    if run.returncode:
        raise MediaError(f"ffmpeg could not decode the audio: {run.stderr.decode(errors='replace')[:200]}")
    return np.frombuffer(run.stdout, dtype=np.float32)


def peaks(samples: np.ndarray, rate: int = SAMPLE_RATE, per_second: int = 50) -> dict:
    """Waveform overview: peak amplitude per bin, 0 to 100, with a square root curve so quiet speech shows."""
    bin_size = max(1, rate // per_second)
    usable = len(samples) // bin_size * bin_size
    if usable == 0:
        return {"rate": per_second, "data": []}
    top = np.abs(samples[:usable]).reshape(-1, bin_size).max(axis=1)
    scale = max(float(np.percentile(top, 99.5)), 1e-4)
    data = np.clip(np.sqrt(top / scale), 0, 1) * 100
    return {"rate": per_second, "data": [int(v) for v in data]}


def make_proxy(path: Path, out: Path, video: bool = True) -> None:
    """A 720p H.264/AAC copy a browser can play."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(path)]
    if video:
        cmd += [
            "-vf",
            "scale=-2:'min(720,ih)',format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
        ]
    else:
        cmd += ["-vn"]
    cmd += ["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)]
    run = subprocess.run(cmd, capture_output=True, text=True)
    if run.returncode:
        raise MediaError(f"proxy encode failed: {run.stderr.strip()[:200]}")
