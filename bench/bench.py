"""Timing for the two things that decide whether Spokecut feels fast.

    python bench/bench.py transcribe VIDEO [--model M ...] [--device cuda|cpu] [--runs 3]
    python bench/bench.py pipeline VIDEO [--model M] [--device cuda|cpu] [--encoder auto|nvenc|x264]
    python bench/bench.py joins VIDEO

`transcribe` loads the model once, runs one warm-up pass that is discarded, then reports the best of N timed
passes as a multiple of the audio length. `pipeline` runs probe, decode, transcribe, snap, cleanup and the MP4
render from a cold start, once, and prints the time of every stage. `joins` renders the same cut list with and
without the 15 ms fade at each join and counts the sample jumps at the joins.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from spokecut import analyze, audio, cleaner, exporting, render, snap, timeline, transcribe
from spokecut.project import load_project, sidecar_path


def hardware() -> dict:
    info = {"python": platform.python_version(), "cpu": platform.processor() or platform.machine()}
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                info["cpu"] = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    try:
        gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if gpu.returncode == 0 and gpu.stdout.strip():
            info["gpu"] = gpu.stdout.strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError):
        pass
    return info


def bench_transcribe(video: Path, models: list[str], device: str, runs: int) -> list[dict]:
    samples = audio.decode_audio(video)
    seconds = len(samples) / snap.SAMPLE_RATE
    rows = []
    for name in models:
        model = transcribe.load_model(name, device)

        def once(model=model):
            started = time.perf_counter()
            segments, _ = model.transcribe(
                samples, word_timestamps=True, condition_on_previous_text=False, vad_filter=False
            )
            count = sum(len(s.words or []) for s in segments)
            return time.perf_counter() - started, count

        once()
        timings = [once() for _ in range(runs)]
        best = min(t for t, _ in timings)
        rows.append(
            {
                "model": name,
                "device": device,
                "audio_seconds": round(seconds, 1),
                "best_seconds": round(best, 2),
                "realtime": round(seconds / best, 1),
                "runs": runs,
                "words": timings[0][1],
            }
        )
        print(json.dumps(rows[-1]), flush=True)
        del model
    return rows


def bench_pipeline(video: Path, model: str | None, device: str, encoder: str) -> dict:
    stages: dict[str, float] = {}
    mark = {"stage": None, "at": time.perf_counter()}
    begun = mark["at"]

    def progress(stage: str, fraction: float) -> None:
        now = time.perf_counter()
        if stage != mark["stage"]:
            if mark["stage"]:
                stages[mark["stage"]] = now - mark["at"]
            mark["stage"], mark["at"] = stage, now

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / video.name
        work.symlink_to(video.resolve())
        project = analyze.analyze(work, model, None, device, progress=progress)
        analysed = time.perf_counter() - begun

        started = time.perf_counter()
        cleaner.apply_cleanup(project, pause=0.7)
        keeps, _ = timeline.plan(project)
        stages["cleanup"] = time.perf_counter() - started

        target = Path(tmp) / "out.mp4"
        started = time.perf_counter()
        exporting.export_project(project, work, "mp4", out=target, encoder=encoder)
        stages["render"] = time.perf_counter() - started
        total = time.perf_counter() - begun
        edited = sum(e - s for s, e in keeps)
        size = target.stat().st_size

    return {
        "media_seconds": round(project.media.duration, 1),
        "edited_seconds": round(edited, 1),
        "model": project.model,
        "device": device,
        "encoder": encoder,
        "stages": {k: round(v, 2) for k, v in stages.items()},
        "analysis_seconds": round(analysed, 2),
        "total_seconds": round(total, 2),
        "realtime": round(project.media.duration / total, 1),
        "output_bytes": size,
    }


def _jumps(video: Path, keeps: list[tuple[float, float]], fade: float, rate: int = 16000) -> dict:
    """Render only the audio of the edit and measure the sample to sample step at every join."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "a.wav"
        script = Path(tmp) / "f.txt"
        graph = render.build_filter(keeps, 0, False, None, fade=fade)
        script.write_text(graph, encoding="utf-8")
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(video),
                "-filter_complex_script",
                str(script),
                "-map",
                "[a]",
                "-ac",
                "1",
                "-ar",
                str(rate),
                str(out),
            ],
            check=True,
        )
        data = audio.decode_audio(out, rate)
    steps = np.abs(np.diff(data))
    edges, at = [], 0.0
    for s, e in keeps[:-1]:
        at += e - s
        edges.append(int(round(at * rate)))
    joins = np.array([steps[max(0, i - 1) : i + 2].max() for i in edges if 0 < i < len(steps)])
    typical = float(np.median(steps)) or 1e-9
    return {
        "fade": fade,
        "joins": int(len(joins)),
        "median_step": round(typical, 5),
        "median_join_step": round(float(np.median(joins)), 5),
        "worst_join_step": round(float(joins.max()), 5),
        "joins_over_10x_median": int((joins > 10 * typical).sum()),
    }


def bench_joins(video: Path) -> list[dict]:
    project = load_project(sidecar_path(video))
    cleaner.apply_cleanup(project, pause=0.7)
    keeps, _ = timeline.plan(project)
    rows = [_jumps(video, keeps, fade) for fade in (0.0, render.FADE)]
    for row in rows:
        print(json.dumps(row), flush=True)
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("transcribe")
    t.add_argument("video", type=Path)
    t.add_argument("--model", action="append")
    t.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    t.add_argument("--runs", type=int, default=3)
    q = sub.add_parser("pipeline")
    q.add_argument("video", type=Path)
    q.add_argument("--model")
    q.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    q.add_argument("--encoder", default="auto")
    j = sub.add_parser("joins")
    j.add_argument("video", type=Path)
    args = p.parse_args(argv)

    print(json.dumps({"hardware": hardware()}), flush=True)
    if args.cmd == "transcribe":
        bench_transcribe(args.video, args.model or ["large-v3-turbo"], args.device, args.runs)
    elif args.cmd == "pipeline":
        print(json.dumps(bench_pipeline(args.video, args.model, args.device, args.encoder), indent=2))
    else:
        bench_joins(args.video)
    return 0


if __name__ == "__main__":
    sys.exit(main())
