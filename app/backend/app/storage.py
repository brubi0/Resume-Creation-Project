"""Filesystem safety for generated documents.

Only UUIDs appear in storage paths. Human-readable names (from candidate or
posting text) live only in Deliverable.filename and in download headers, and are
always passed through safe_component.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import quote

from app.config import settings


def safe_component(text: str | None, fallback: str, max_len: int = 60) -> str:
    s = unicodedata.normalize("NFKC", str(text or ""))
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")
    for sep in ("/", "\\", "\x00"):
        s = s.replace(sep, "")
    s = s.replace("'", "").replace("’", "").replace("‘", "")
    s = re.sub(r"\s+", "_", s)
    s = "".join(ch for ch in s if ch.isalnum() or ch in "-_.")
    while ".." in s:
        s = s.replace("..", "")
    s = re.sub(r"([_.-])\1+", r"\1", s)
    s = s.lstrip(".").strip("_")
    s = s[:max_len].rstrip("._-")
    return s or fallback


def deliverables_root() -> Path:
    return Path(settings.DELIVERABLES_DIR)


def session_dir(session_id: uuid.UUID) -> Path:
    return deliverables_root() / str(uuid.UUID(str(session_id)))


def resolve_inside(base: str | Path, name: str | Path) -> Path:
    """Resolve base/name (name may be absolute) and require it to stay inside base."""
    base_r = Path(base).resolve()
    target = (base_r / name).resolve()
    if target != base_r and base_r not in target.parents:
        raise ValueError("path escapes the storage directory")
    return target


def storage_name(deliverable_id: uuid.UUID, ext: str) -> str:
    ext = ext if ext.startswith(".") else f".{ext}"
    return f"{uuid.UUID(str(deliverable_id))}{ext}"


def download_name(candidate: str | None, label: str, ext: str, *parts: str | None) -> str:
    """e.g. download_name("Maria Santos", "Resume_FINAL", "docx") -> Maria_Santos_Resume_FINAL.docx"""
    ext = ext if ext.startswith(".") else f".{ext}"
    pieces = [safe_component(candidate, "Candidate"), label]
    pieces += [safe_component(p, "") for p in parts if safe_component(p, "")]
    stem = "_".join(pieces)[: 120 - len(ext)].rstrip("._-")
    return stem + ext


def content_disposition(filename: str) -> str:
    """Attachment header with an ASCII fallback plus RFC 5987 filename*."""
    ascii_name = "".join(
        ch if (ch.isascii() and (ch.isalnum() or ch in "-_.")) else "_" for ch in filename
    ) or "download"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"
