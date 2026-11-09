"""The projects the server has open. A project is a video file plus the sidecar next to it."""

from __future__ import annotations

import hashlib
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .project import Project, load_project, sidecar_path

SAFE_NAME = re.compile(r"[^\w .,'()&+-]+", re.UNICODE)


def default_upload_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "spokecut" / "uploads"


def clean_filename(name: str) -> str:
    stem = SAFE_NAME.sub("", Path(name).stem).strip()[:80] or "video"
    suffix = re.sub(r"[^\w.]", "", Path(name).suffix)[:8].lower()
    return stem + suffix


@dataclass
class Entry:
    id: str
    video: Path
    project: Project | None = None
    status: str = "new"  # new, analyzing, ready, error
    error: str = ""
    job_id: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def name(self) -> str:
        return self.video.name

    def summary(self) -> dict:
        media = self.project.media if self.project else None
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "error": self.error,
            "jobId": self.job_id,
            "duration": media.duration if media else None,
            "hasVideo": media.has_video if media else None,
        }


class Workspace:
    def __init__(self, upload_dir: Path | None = None) -> None:
        self.upload_dir = upload_dir or default_upload_dir()
        self.entries: dict[str, Entry] = {}
        self._lock = threading.Lock()

    @staticmethod
    def key(video: Path) -> str:
        return hashlib.sha1(str(video.resolve()).encode()).hexdigest()[:12]

    def open(self, video: Path) -> Entry:
        """Register a video, loading its sidecar if one exists. Returns the existing entry on a repeat call."""
        video = video.expanduser().resolve()
        if not video.is_file():
            raise FileNotFoundError(f"no such file: {video}")
        key = self.key(video)
        with self._lock:
            entry = self.entries.get(key)
            if entry is None:
                entry = self.entries[key] = Entry(key, video)
                sidecar = sidecar_path(video)
                if sidecar.is_file():
                    try:
                        entry.project, entry.status = load_project(sidecar), "ready"
                    except (ValueError, KeyError, OSError):
                        entry.status = "new"  # unreadable sidecar: analyze again, the old file is left in place
            return entry

    def get(self, project_id: str) -> Entry | None:
        return self.entries.get(project_id)

    def upload_path(self, name: str, token: str) -> Path:
        folder = self.upload_dir / token
        folder.mkdir(parents=True, exist_ok=True)
        return folder / clean_filename(name)
