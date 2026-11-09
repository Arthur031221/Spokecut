"""Rebuild web/demo/clip.mp4 and web/demo/project.json from the Commons source video.

    python scripts/build_demo.py [--model large-v3]

Needs ffmpeg and the spokecut package. Downloads about 25 MB. See web/demo/NOTICE for the license.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from spokecut import analyze
from spokecut.project import sidecar_path

SOURCE = "https://upload.wikimedia.org/wikipedia/commons/3/31/Ward_Cunningham%2C_Inventor_of_the_Wiki.webm"
START, END = 73.9, 154.2
OUT = Path(__file__).resolve().parent.parent / "web" / "demo"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="large-v3")
    p.add_argument("--out", type=Path, default=OUT, help="where to write clip.mp4 and project.json")
    args = p.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "source.webm"
        request = urllib.request.Request(SOURCE, headers={"User-Agent": "spokecut-build-demo"})
        with urllib.request.urlopen(request) as response, src.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        clip = Path(tmp) / "clip.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", str(START), "-to", str(END), "-i", str(src)]
            + ["-vf", "scale=-2:540", "-c:v", "libx264", "-crf", "27", "-preset", "slow", "-g", "30"]
            + ["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k", "-ac", "1", "-movflags", "+faststart", str(clip)],
            check=True,
        )
        analyze.analyze(clip, model=args.model, language="en")
        args.out.mkdir(parents=True, exist_ok=True)
        shutil.copy(clip, args.out / "clip.mp4")
        shutil.copy(sidecar_path(clip), args.out / "project.json")
    print(f"wrote {args.out / 'clip.mp4'} and {args.out / 'project.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
