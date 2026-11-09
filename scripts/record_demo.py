"""Record the README demo: drive the live demo page in a real browser and turn the video into assets/demo.gif.

    python scripts/record_demo.py            # needs Chrome (or Playwright's Chromium) and ffmpeg

The interaction is real. The page plays the bundled clip and skips the cut parts, the same way the editor does.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
SIZE = {"width": 1280, "height": 800}


def serve(directory: Path) -> tuple[uvicorn.Server, str]:
    """A static server that answers Range requests, which a browser needs to seek in the clip."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    app = Starlette(routes=[Mount("/", StaticFiles(directory=directory, html=True))])
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=srv.run, daemon=True).start()
    while not srv.started:
        time.sleep(0.05)
    return srv, f"http://localhost:{port}/?demo"


def word(page, i: int):
    return page.locator(f'.w[data-i="{i}"]')


def perform(page, url: str) -> None:
    page.goto(url)
    page.wait_for_selector("#editor:not([hidden])", timeout=30000)
    page.wait_for_timeout(1800)
    page.click("#pause-apply")  # cut every long pause
    page.wait_for_timeout(1700)
    page.click('[data-kind="filler"] .main')  # and the fillers
    page.wait_for_timeout(1500)
    page.keyboard.press("Control+f")  # find a word and cut every match
    page.keyboard.type("about", delay=140)
    page.wait_for_timeout(1300)
    page.click("#find-cut")
    page.wait_for_timeout(1600)
    page.fill("#find-input", "")
    word(page, 30).click()  # drag out a sentence
    word(page, 45).click(modifiers=["Shift"])
    page.wait_for_timeout(1000)
    page.keyboard.press("Delete")
    page.wait_for_timeout(1700)
    page.keyboard.press("Home")
    page.click("#play")  # hear the edit, with the cuts skipped
    page.wait_for_timeout(5200)
    page.click("#play")
    page.click("#tab-captions")
    page.locator('input[value="karaoke"]').check(force=True)
    page.wait_for_timeout(1500)
    page.click("#tab-export")
    page.wait_for_timeout(1700)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "assets" / "demo.gif")
    ap.add_argument("--channel", default="chrome")
    args = ap.parse_args()

    srv, url = serve(ROOT / "web")
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        launch = {"args": ["--autoplay-policy=no-user-gesture-required"]}
        try:
            browser = p.chromium.launch(channel=args.channel, **launch)
        except Exception:
            browser = p.chromium.launch(**launch)
        context = browser.new_context(viewport=SIZE, record_video_dir=tmp, record_video_size=SIZE)
        page = context.new_page()
        perform(page, url)
        context.close()
        browser.close()
        video = next(Path(tmp).glob("*.webm"))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        palette = Path(tmp) / "palette.png"
        scale = "fps=10,scale=900:-1:flags=lanczos"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf", f"{scale},palettegen=max_colors=96", str(palette)],
            check=True,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(palette)]
            + ["-lavfi", f"{scale}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4", str(args.out)],
            check=True,
        )
    srv.should_exit = True
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
