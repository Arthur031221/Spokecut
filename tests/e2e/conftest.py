"""Browser fixtures: the static demo behind a range-capable file server, and the real server with a stub transcriber."""

from __future__ import annotations

import json
import os
import shutil
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from spokecut import server
from spokecut.project import Project, save_project, sidecar_path
from spokecut.server import Config, create_app

WEB = Path(__file__).resolve().parents[2] / "web"
TOKEN = "e2e-token"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(app) -> tuple[uvicorn.Server, threading.Thread, int]:
    port = free_port()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not srv.started and time.time() < deadline:
        time.sleep(0.05)
    return srv, thread, port


@pytest.fixture(scope="session")
def demo_url():
    # Starlette answers Range requests, which a browser needs to seek. http.server does not.
    srv, thread, port = serve(Starlette(routes=[Mount("/", StaticFiles(directory=WEB, html=True))]))
    yield f"http://localhost:{port}/?demo"
    srv.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def demo_project() -> dict:
    return json.loads((WEB / "demo" / "project.json").read_text())


@pytest.fixture
def analysis_calls() -> list[dict]:
    """The options every transcription was started with."""
    return []


@pytest.fixture
def server_url(tmp_path, monkeypatch, demo_project, analysis_calls):
    def fake_analyze(video, model=None, language=None, device="auto", verbatim=False, progress=None, proxy_dir=None):
        """The demo transcript for whatever was uploaded, so the browser sees real data without Whisper."""
        analysis_calls.append({"video": video.name, "model": model, "language": language, "verbatim": verbatim})
        if video.name.startswith("broken"):
            raise RuntimeError("the model could not be loaded")
        data = json.loads(json.dumps(demo_project))
        data["media"]["file"] = video.name
        project = Project.from_json(data)
        save_project(project, sidecar_path(video))
        return project

    monkeypatch.setattr(server, "analyze", fake_analyze)
    app = create_app(Config(token=TOKEN, upload_dir=tmp_path / "uploads"))
    srv, thread, port = serve(app)
    yield f"http://localhost:{port}"
    srv.should_exit = True
    thread.join(timeout=5)
    app.state.jobs.close()


@pytest.fixture(scope="session")
def clip(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("clip") / "talk.mp4"
    shutil.copy(WEB / "demo" / "clip.mp4", path)
    return path


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    args = ["--autoplay-policy=no-user-gesture-required"]
    channel = os.environ.get("SPOKECUT_BROWSER_CHANNEL")
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel=channel, args=args) if channel else p.chromium.launch(args=args)
        except Exception:
            b = p.chromium.launch(channel="chrome", args=args)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1360, "height": 900}, accept_downloads=True)
    page = context.new_page()
    page.problems = []
    page.on("pageerror", lambda e: page.problems.append(f"pageerror: {e}"))
    page.on("console", lambda m: page.problems.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
    yield page
    context.close()
