"""The local web server: a small JSON API, the media file with range support and the static editor."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import urllib.parse
import uuid
from dataclasses import dataclass
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import __version__, transcribe
from .analyze import analyze
from .audio import MediaError, require_ffmpeg
from .exporting import FORMATS, export_project
from .jobs import Job, JobQueue
from .project import save_project, sidecar_path, validate_state
from .workspace import Entry, Workspace

MAX_UPLOAD = 8 << 30  # 8 GiB: talking-head recordings are big, and the file stays on this machine
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}
COOKIE = "spokecut_token"
LANGUAGE = re.compile(r"^[a-z]{2,3}$")


def check_options(model: object, language: object) -> tuple[str | None, str | None]:
    """The model and language a browser asked for, or a 422 when they are not something Spokecut offers."""
    model = model or None
    language = language or None
    if model is not None and model not in transcribe.WHISPER_MODELS:
        raise HTTPException(422, f"model must be one of {', '.join(transcribe.WHISPER_MODELS)}")
    if language is not None and not (isinstance(language, str) and LANGUAGE.match(language)):
        raise HTTPException(422, "language must be a code such as en or zh")
    return model, language


def error_response(request: Request, exc: Exception) -> Response:
    """Errors as JSON with a `detail`, which is what the editor reads to tell the user what went wrong."""
    assert isinstance(exc, HTTPException)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@dataclass
class Config:
    model: str | None = None
    language: str | None = None
    device: str = "auto"
    verbatim: bool = False
    token: str = ""
    extra_hosts: frozenset[str] = frozenset()
    upload_dir: Path | None = None
    start_worker: bool = True


def web_root() -> Path:
    packaged = Path(__file__).parent / "web"
    return packaged if packaged.is_dir() else Path(__file__).resolve().parents[2] / "web"


def hostname(host_header: str) -> str:
    """Strip the port from a Host header value, keeping bracketed IPv6 literals intact."""
    if host_header.startswith("["):
        return host_header.split("]")[0] + "]"
    return host_header.rsplit(":", 1)[0] if ":" in host_header else host_header


class LocalOnly:
    """Reject requests whose Host or Origin is not this machine (DNS rebinding, cross-site writes)."""

    def __init__(self, app, extra_hosts: frozenset[str]):
        self.app = app
        self.allowed = LOCAL_HOSTS | set(extra_hosts)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            raw_host = headers.get("host", "")
            origin = headers.get("origin")
            bad_origin = origin is not None and origin.split("://", 1)[-1] != raw_host
            if hostname(raw_host) not in self.allowed or bad_origin:
                response = JSONResponse({"error": "forbidden host"}, status_code=403)
                return await response(scope, receive, send)
        return await self.app(scope, receive, send)


def create_app(config: Config | None = None, workspace: Workspace | None = None) -> Starlette:
    config = config or Config()
    token = config.token or secrets.token_urlsafe(18)
    workspace = workspace or Workspace(config.upload_dir)
    jobs = JobQueue() if config.start_worker else None
    root = web_root()

    def authorized(request: Request) -> bool:
        given = request.headers.get("x-spokecut-token") or request.cookies.get(COOKIE) or ""
        return secrets.compare_digest(given.encode(), token.encode())

    def guard(request: Request) -> None:
        if not authorized(request):
            raise HTTPException(401, "missing or wrong token. Open the address Spokecut printed in the terminal.")

    def entry_or_404(project_id: str) -> Entry:
        entry = workspace.get(project_id)
        if entry is None:
            raise HTTPException(404, "no such project")
        return entry

    def ready(entry: Entry) -> Entry:
        if entry.project is None or entry.status != "ready":
            raise HTTPException(409, "the transcript is not ready yet")
        return entry

    def start_analysis(entry: Entry, model: str | None, language: str | None, verbatim: bool) -> Job:
        if jobs is None:
            raise HTTPException(503, "no worker is running")
        running = jobs.active(entry.id, "analyze")
        if running:
            return running

        def run(job: Job) -> None:
            try:
                entry.project = analyze(
                    entry.video,
                    model or config.model,
                    language or config.language,
                    config.device,
                    verbatim,
                    job.report,
                )
                entry.status, entry.error = "ready", ""
            except Exception as exc:
                # A failed second transcription leaves the first one, and its edit, where it was.
                entry.status = "ready" if entry.project is not None else "error"
                entry.error = str(exc) or exc.__class__.__name__
                raise

        entry.status, entry.error = "analyzing", ""
        job = jobs.submit("analyze", entry.id, run)
        entry.job_id = job.id
        return job

    def open_video(
        video: Path, model: str | None = None, language: str | None = None, verbatim: bool | None = None
    ) -> Entry:
        """Register a video and start transcribing it unless a sidecar already holds the transcript."""
        entry = workspace.open(video)
        if entry.status == "new" or (entry.status == "error" and jobs and not jobs.active(entry.id)):
            start_analysis(entry, model, language, config.verbatim if verbatim is None else verbatim)
        return entry

    def entry_response(entry: Entry) -> Response:
        return JSONResponse(entry.summary(), status_code=202 if entry.status == "analyzing" else 200)

    async def health(request: Request) -> Response:
        try:
            require_ffmpeg()
            ffmpeg = True
        except MediaError:
            ffmpeg = False
        return JSONResponse(
            {
                "version": __version__,
                "authorized": authorized(request),
                "ffmpeg": ffmpeg,
                "cuda": transcribe.has_cuda(),
                "formats": list(FORMATS),
            }
        )

    async def home(request: Request) -> Response:
        supplied = request.query_params.get("t")
        if supplied is not None and secrets.compare_digest(supplied.encode(), token.encode()):
            response = RedirectResponse("/", status_code=303)
            response.set_cookie(COOKIE, token, httponly=True, samesite="strict", path="/")
            return response
        return FileResponse(root / "index.html")

    async def list_projects(request: Request) -> Response:
        guard(request)
        return JSONResponse([e.summary() for e in workspace.entries.values()])

    async def open_path(request: Request) -> Response:
        guard(request)
        body = await request.json()
        path = Path(str(body.get("path", ""))).expanduser()
        model, language = check_options(body.get("model"), body.get("language"))
        verbatim = bool(body["verbatim"]) if "verbatim" in body else None
        try:
            entry = await run_in_threadpool(open_video, path, model, language, verbatim)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        return entry_response(entry)

    async def upload(request: Request) -> Response:
        guard(request)
        name = request.query_params.get("name", "video.mp4")
        model, language = check_options(request.query_params.get("model"), request.query_params.get("language"))
        verbatim = request.query_params.get("verbatim") == "1" if "verbatim" in request.query_params else None
        workspace.upload_dir.mkdir(parents=True, exist_ok=True)
        tmp = workspace.upload_dir / f".upload-{uuid.uuid4().hex}"
        digest, size = hashlib.sha1(), 0
        try:
            with open(tmp, "wb") as fh:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise HTTPException(413, "file is larger than 8 GiB")
                    digest.update(chunk)
                    fh.write(chunk)
            if size == 0:
                raise HTTPException(400, "empty upload")
            target = workspace.upload_path(name, digest.hexdigest()[:12])
            if not target.exists():
                tmp.replace(target)
        finally:
            tmp.unlink(missing_ok=True)
        return entry_response(await run_in_threadpool(open_video, target, model, language, verbatim))

    async def get_project(request: Request) -> Response:
        guard(request)
        entry = entry_or_404(request.path_params["project_id"])
        body = entry.summary()
        job = jobs.jobs.get(entry.job_id) if jobs and entry.job_id else None
        body["job"] = job.to_json() if job else None
        body["project"] = entry.project.to_json() if entry.project and entry.status == "ready" else None
        return JSONResponse(body)

    async def reanalyze(request: Request) -> Response:
        guard(request)
        entry = entry_or_404(request.path_params["project_id"])
        body = await request.json() if await request.body() else {}
        model, language = check_options(body.get("model"), body.get("language"))
        job = start_analysis(entry, model, language, bool(body.get("verbatim", False)))
        return JSONResponse(job.to_json(), status_code=202)

    async def put_state(request: Request) -> Response:
        guard(request)
        entry = ready(entry_or_404(request.path_params["project_id"]))
        try:
            state = validate_state(await request.json(), len(entry.project.words))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

        def store() -> None:
            # The lock is taken in the worker thread, so waiting for it never blocks the event loop.
            with entry.lock:
                entry.project.state = state
                save_project(entry.project, sidecar_path(entry.video))

        await run_in_threadpool(store)
        return Response(status_code=204)

    async def media(request: Request) -> Response:
        guard(request)
        entry = ready(entry_or_404(request.path_params["project_id"]))
        proxy = entry.project.media.proxy
        path = entry.video.with_name(proxy) if proxy else entry.video
        if not path.is_file():
            raise HTTPException(404, "the media file moved or was deleted")
        return FileResponse(path)

    def download(body: bytes | str | Path, name: str, mime: str) -> Response:
        ascii_name = json.dumps(name.encode("ascii", "replace").decode())
        disposition = f"attachment; filename={ascii_name}; filename*=UTF-8''{urllib.parse.quote(name)}"
        if isinstance(body, Path):
            return FileResponse(body, media_type=mime, headers={"Content-Disposition": disposition})
        return Response(body, media_type=f"{mime}; charset=utf-8", headers={"Content-Disposition": disposition})

    async def export_text(request: Request) -> Response:
        guard(request)
        entry = ready(entry_or_404(request.path_params["project_id"]))
        fmt = request.path_params["fmt"]
        if fmt not in FORMATS or fmt == "mp4":
            raise HTTPException(404, "unknown export format")
        result = await run_in_threadpool(export_project, entry.project, entry.video, fmt)
        return download(result.text or "", result.filename, result.mime)

    async def start_render(request: Request) -> Response:
        guard(request)
        entry = ready(entry_or_404(request.path_params["project_id"]))
        if jobs is None:
            raise HTTPException(503, "no worker is running")
        running = jobs.active(entry.id, "render")
        if running:
            return JSONResponse(running.to_json(), status_code=202)
        body = await request.json() if await request.body() else {}
        encoder = body.get("encoder", "auto")
        if encoder not in ("auto", "nvenc", "x264"):
            raise HTTPException(422, "encoder must be auto, nvenc or x264")

        def run(job: Job):
            job.report("render", 0.0)
            return export_project(
                entry.project, entry.video, "mp4", encoder=encoder, progress=lambda f: job.report("render", f)
            )

        return JSONResponse(jobs.submit("render", entry.id, run).to_json(), status_code=202)

    async def get_job(request: Request) -> Response:
        guard(request)
        job = jobs.jobs.get(request.path_params["job_id"]) if jobs else None
        if job is None:
            raise HTTPException(404, "no such job")
        return JSONResponse(job.to_json())

    async def job_file(request: Request) -> Response:
        guard(request)
        job = jobs.jobs.get(request.path_params["job_id"]) if jobs else None
        if job is None or job.status != "done" or job.result is None or job.result.path is None:
            raise HTTPException(404, "nothing to download")
        return download(job.result.path, job.result.filename, job.result.mime)

    routes = [
        Route("/", home),
        Route("/api/health", health),
        Route("/api/projects", list_projects, methods=["GET"]),
        Route("/api/open", open_path, methods=["POST"]),
        Route("/api/upload", upload, methods=["POST"]),
        Route("/api/projects/{project_id}", get_project, methods=["GET"]),
        Route("/api/projects/{project_id}/analyze", reanalyze, methods=["POST"]),
        Route("/api/projects/{project_id}/state", put_state, methods=["PUT"]),
        Route("/api/projects/{project_id}/media", media, methods=["GET"]),
        Route("/api/projects/{project_id}/export/{fmt}", export_text, methods=["GET"]),
        Route("/api/projects/{project_id}/render", start_render, methods=["POST"]),
        Route("/api/jobs/{job_id}", get_job, methods=["GET"]),
        Route("/api/jobs/{job_id}/file", job_file, methods=["GET"]),
        Mount("/", StaticFiles(directory=root, html=True), name="web"),
    ]
    app = Starlette(
        routes=routes,
        middleware=[Middleware(LocalOnly, extra_hosts=config.extra_hosts)],
        exception_handlers={HTTPException: error_response},
    )
    app.state.token, app.state.workspace, app.state.jobs = token, workspace, jobs
    app.state.open_video = open_video
    return app
