import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from conftest import make_project, needs_ffmpeg
from starlette.testclient import TestClient

from spokecut import server
from spokecut.project import Media, save_project, sidecar_path
from spokecut.server import Config, create_app

TOKEN = "t0ken"


def fake_analyze(video, model=None, language=None, device="auto", verbatim=False, progress=None, proxy_dir=None):
    """Stands in for Whisper: the same words every time, saved like the real pipeline does."""
    project = make_project()
    project.media = Media(video.name, 20.0, 30.0, 1280, 720, True)
    project.model = model or "fake"
    if progress:
        progress("transcribe", 0.5)
    save_project(project, sidecar_path(video))
    return project


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "analyze", fake_analyze)
    return create_app(Config(token=TOKEN, upload_dir=tmp_path / "uploads"))


@pytest.fixture
def client(app):
    c = TestClient(app, base_url="http://localhost")
    c.headers["x-spokecut-token"] = TOKEN
    return c


@pytest.fixture
def video(tmp_path) -> Path:
    path = tmp_path / "talk.mp4"
    path.write_bytes(b"not really a video " * 100)
    return path


def wait(client, project_id, status="ready", timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        body = client.get(f"/api/projects/{project_id}").json()
        if body["status"] == status:
            return body
        time.sleep(0.02)
    raise AssertionError(f"project never became {status}: {body}")


def open_video(client, video):
    r = client.post("/api/open", json={"path": str(video)})
    assert r.status_code in (200, 202), r.text
    return r.json()["id"]


def test_api_needs_the_token(app, video):
    bare = TestClient(app, base_url="http://localhost")
    assert bare.get("/api/projects").status_code == 401
    assert bare.post("/api/open", json={"path": str(video)}).status_code == 401
    wrong = TestClient(app, base_url="http://localhost", headers={"x-spokecut-token": "nope"})
    assert wrong.get("/api/projects").status_code == 401


def test_token_in_the_address_becomes_a_cookie(app):
    c = TestClient(app, base_url="http://localhost", follow_redirects=False)
    r = c.get(f"/?t={TOKEN}")
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert "HttpOnly" in r.headers["set-cookie"] and "SameSite=strict" in r.headers["set-cookie"]
    assert c.get("/api/projects").status_code == 200  # the cookie alone is enough


def test_wrong_token_in_the_address_sets_no_cookie(app):
    r = TestClient(app, base_url="http://localhost", follow_redirects=False).get("/?t=bad")
    assert r.status_code == 200 and "set-cookie" not in r.headers


def test_foreign_host_and_origin_are_refused(app):
    evil = TestClient(app, base_url="http://evil.example", headers={"x-spokecut-token": TOKEN})
    assert evil.get("/api/health").status_code == 403
    local = TestClient(app, base_url="http://localhost", headers={"x-spokecut-token": TOKEN})
    assert local.get("/api/health", headers={"origin": "http://evil.example"}).status_code == 403
    assert local.get("/api/health", headers={"origin": "http://localhost"}).status_code == 200


def test_health_is_public_but_says_whether_you_are_in(app):
    r = TestClient(app, base_url="http://localhost").get("/api/health")
    assert r.status_code == 200 and r.json()["authorized"] is False


def test_open_transcribes_then_serves_the_project(client, video):
    pid = open_video(client, video)
    body = wait(client, pid)
    assert body["project"]["language"] == "en" and len(body["project"]["words"]) > 10
    assert sidecar_path(video).is_file()


def test_open_is_idempotent(client, video):
    assert open_video(client, video) == open_video(client, video)
    wait(client, open_video(client, video))
    assert len(client.get("/api/projects").json()) == 1


def test_open_reuses_an_existing_sidecar(client, video):
    fake_analyze(video)
    r = client.post("/api/open", json={"path": str(video)})
    assert r.status_code == 200 and r.json()["status"] == "ready"


def test_open_missing_file(client, tmp_path):
    assert client.post("/api/open", json={"path": str(tmp_path / "nope.mp4")}).status_code == 404


def test_upload_stores_the_file_and_deduplicates(client, video):
    data = video.read_bytes()
    a = client.post("/api/upload?name=My%20Talk.mp4", content=data)
    b = client.post("/api/upload?name=My%20Talk.mp4", content=data)
    assert a.status_code in (200, 202) and a.json()["id"] == b.json()["id"]
    assert wait(client, a.json()["id"])["name"] == "My Talk.mp4"
    assert client.post("/api/upload?name=x.mp4", content=b"").status_code == 400


def test_upload_name_cannot_escape_the_folder(client, video, tmp_path):
    r = client.post("/api/upload?name=../../evil.mp4", content=video.read_bytes())
    pid = r.json()["id"]
    assert wait(client, pid)["name"] == "evil.mp4"
    assert not (tmp_path.parent / "evil.mp4").exists()


def test_state_round_trip_and_sidecar(client, video):
    pid = open_video(client, video)
    wait(client, pid)
    state = {"deleted": [1, 5], "cutGaps": [9], "edits": {"0": "Thus"}, "pause": {"threshold": 0.8, "keep": 0.3}}
    assert client.put(f"/api/projects/{pid}/state", json=state).status_code == 204
    got = client.get(f"/api/projects/{pid}").json()["project"]["state"]
    assert got["deleted"] == [1, 5] and got["edits"] == {"0": "Thus"} and got["pause"]["keep"] == 0.3
    assert json.loads(sidecar_path(video).read_text())["state"]["deleted"] == [1, 5]


@pytest.mark.parametrize(
    "bad",
    [
        {"deleted": [999]},
        {"deleted": ["1"]},
        {"deleted": [True]},
        {"cutGaps": [-1]},
        {"edits": {"0": 5}},
        {"edits": {"abc": "x"}},
        {"pause": {"keep": 99}},
        {"caption": {"style": "comic"}},
        {"caption": {"color": "red"}},
        {"caption": {"size": 400}},
        {"pause": 5},
        {"caption": "plain"},
        [],
    ],
)
def test_bad_state_is_rejected_and_nothing_is_saved(client, video, bad):
    pid = open_video(client, video)
    wait(client, pid)
    before = client.get(f"/api/projects/{pid}").json()["project"]["state"]
    assert client.put(f"/api/projects/{pid}/state", json=bad).status_code == 422
    assert client.get(f"/api/projects/{pid}").json()["project"]["state"] == before


def test_media_supports_range_requests(client, video):
    pid = open_video(client, video)
    wait(client, pid)
    r = client.get(f"/api/projects/{pid}/media", headers={"range": "bytes=4-9"})
    assert r.status_code == 206 and r.content == video.read_bytes()[4:10]


def test_media_prefers_the_proxy(client, video):
    pid = open_video(client, video)
    wait(client, pid)
    (video.parent / "talk.spokecut-proxy.mp4").write_bytes(b"proxy")
    client.app.state.workspace.get(pid).project.media.proxy = "talk.spokecut-proxy.mp4"
    assert client.get(f"/api/projects/{pid}/media").content == b"proxy"


def test_text_exports_download(client, video):
    pid = open_video(client, video)
    wait(client, pid)
    client.put(f"/api/projects/{pid}/state", json={"deleted": [1]})
    srt = client.get(f"/api/projects/{pid}/export/srt")
    assert srt.status_code == 200 and "talk.spokecut.srt" in srt.headers["content-disposition"]
    assert " um " not in srt.text
    for fmt in ("vtt", "ass", "edl", "fcpxml", "otio", "json"):
        assert client.get(f"/api/projects/{pid}/export/{fmt}").status_code == 200
    assert client.get(f"/api/projects/{pid}/export/mp4").status_code == 404
    assert client.get(f"/api/projects/{pid}/export/doc").status_code == 404


def test_export_before_the_transcript_is_ready_is_a_conflict(client, video, monkeypatch):
    monkeypatch.setattr(server, "analyze", lambda *a, **k: time.sleep(0.5) or fake_analyze(a[0]))
    pid = open_video(client, video)
    assert client.get(f"/api/projects/{pid}/export/srt").status_code == 409


def test_failed_transcription_is_reported(client, video, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("model not found")

    monkeypatch.setattr(server, "analyze", boom)
    pid = open_video(client, video)
    body = wait(client, pid, "error")
    assert body["error"] == "model not found" and body["job"]["status"] == "error"


def test_unknown_project_and_job(client):
    assert client.get("/api/projects/nope").status_code == 404
    assert client.get("/api/jobs/nope").status_code == 404


def test_static_editor_is_served(client):
    assert client.get("/").status_code == 200


@needs_ffmpeg
def test_render_job_produces_a_download(app, client, tone_video, monkeypatch):
    def analyze_tone(video, *a, **k):
        project = make_project(duration=3.0)
        project.words = project.words[:6]
        project.snaps = project.snaps[:6] + [3.0]
        project.media = Media(video.name, 3.0, 30.0, 320, 240, True)
        save_project(project, sidecar_path(video))
        return project

    monkeypatch.setattr(server, "analyze", analyze_tone)
    pid = open_video(client, tone_video)
    wait(client, pid)
    client.put(f"/api/projects/{pid}/state", json={"deleted": [1], "caption": {"burn": False}})
    job = client.post(f"/api/projects/{pid}/render", json={"encoder": "x264"}).json()
    end = time.time() + 30
    while time.time() < end and client.get(f"/api/jobs/{job['id']}").json()["status"] not in ("done", "error"):
        time.sleep(0.05)
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "done"
    r = client.get(f"/api/jobs/{job['id']}/file")
    assert r.status_code == 200 and r.content[4:8] == b"ftyp"
    assert client.post(f"/api/projects/{pid}/render", json={"encoder": "bad"}).status_code == 422


def test_overlapping_saves_do_not_freeze_the_server(client, video, monkeypatch):
    """Two saves of one project in flight on one event loop, as when a tab closes mid save, must both finish."""
    import asyncio

    import httpx

    pid = open_video(client, video)
    wait(client, pid)
    real = server.save_project

    def slow_save(*args):
        time.sleep(0.2)
        real(*args)

    monkeypatch.setattr(server, "save_project", slow_save)

    async def put_three():
        transport = httpx.ASGITransport(app=client.app)
        headers = {"x-spokecut-token": TOKEN}
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost", headers=headers) as c:
            calls = [c.put(f"/api/projects/{pid}/state", json={"deleted": [i]}) for i in (1, 2, 3)]
            return [r.status_code for r in await asyncio.wait_for(asyncio.gather(*calls), timeout=5)]

    # A thread of its own, because the browser tests leave an event loop running in this one.
    with ThreadPoolExecutor(1) as pool:
        assert pool.submit(asyncio.run, put_three()).result(timeout=10) == [204, 204, 204]
