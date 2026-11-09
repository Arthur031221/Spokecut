"""One worker thread runs transcription and rendering, one job at a time, so GPU memory stays predictable."""

from __future__ import annotations

import queue
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Job:
    kind: str
    project_id: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "queued"  # queued, running, done, error
    stage: str = "queued"
    progress: float = 0.0
    error: str = ""
    result: Any = None

    def report(self, stage: str, fraction: float = 0.0) -> None:
        self.stage, self.progress = stage, max(0.0, min(1.0, fraction))

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "projectId": self.project_id,
            "status": self.status,
            "stage": self.stage,
            "progress": round(self.progress, 3),
            "error": self.error,
        }


class JobQueue:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self._queue: queue.Queue[tuple[Job, Callable[[Job], Any]] | None] = queue.Queue()
        self._thread = threading.Thread(target=self._work, name="spokecut-worker", daemon=True)
        self._thread.start()

    def submit(self, kind: str, project_id: str, run: Callable[[Job], Any]) -> Job:
        job = Job(kind, project_id)
        self.jobs[job.id] = job
        self._queue.put((job, run))
        return job

    def active(self, project_id: str, kind: str | None = None) -> Job | None:
        for job in self.jobs.values():
            if job.project_id == project_id and job.status in ("queued", "running") and kind in (None, job.kind):
                return job
        return None

    def _work(self) -> None:
        while (item := self._queue.get()) is not None:
            job, run = item
            job.status = "running"
            try:
                job.result = run(job)
                job.status, job.stage, job.progress = "done", "done", 1.0
            except Exception as exc:  # the worker must outlive any single failing job
                job.status, job.stage, job.error = "error", "error", str(exc) or exc.__class__.__name__

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join(timeout=5)
