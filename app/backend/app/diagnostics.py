"""Read-only data-integrity diagnostics.  Run:  python -m app.diagnostics [--json]

Prints counts and session/deliverable UUIDs only: never names, messages, answers or
document content. The whole run is one READ ONLY transaction, so it cannot change
data. Always exits 0 (it reports; it does not gate).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.interview import discovery_complete_for

KNOWN_STATUSES = ("active", "interview_complete", "deliverables_generated", "abandoned")
REQUIRED_BASE_TYPES = ("resume_md", "resume_docx", "interview_prep_md",
                       "skills_matrix_html", "score_card_md")
LEGACY_TYPES = {
    "resume": "resume_docx",
    "interview_prep": "interview_prep_md",
    "skills_matrix": "skills_matrix_html",
    "score_card": "score_card_md",
}
# resume_md has no legacy twin: legacy sessions only ever had the DOCX resume, so a
# legacy `resume` row satisfies both resume_md and resume_docx.
LEGACY_SATISFIES = {"resume": ("resume_md", "resume_docx")}
RUNNING_STALE_MINUTES = 30
IGNORED_FILES = {"discovery.md"}
IGNORED_DIRS = {".staging"}


def _ids(values) -> list[str]:
    return sorted(str(v) for v in values)


def _entry(ids: list[str]) -> dict:
    return {"count": len(ids), "ids": ids}


def _files_on_disk(root: Path) -> list[Path]:
    out: list[Path] = []
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for fn in filenames:
            if fn in IGNORED_FILES:
                continue
            out.append(Path(dirpath) / fn)
    return out


_UUID_PART = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(\.[A-Za-z0-9]{1,8})?$")


def _safe_rel(path: Path, root: Path) -> str:
    """Relative path with every non-UUID component masked: legacy files carry candidate names."""
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = (path.name,)
    return "/".join(p if _UUID_PART.match(p) else "<non-uuid-name>" + (Path(p).suffix or "") for p in parts)


async def collect() -> dict:
    root = Path(settings.DELIVERABLES_DIR)
    findings: dict[str, dict] = {}
    async with engine.connect() as conn:
        await conn.execute(text("SET TRANSACTION READ ONLY"))

        sessions = (await conn.execute(text(
            "SELECT id, user_id, phase, status, experience_level, discovery_data, "
            "generation_status, generation_started_at, "
            "(generation_started_at < now() - make_interval(mins => :m)) AS stale "
            "FROM sessions"
        ), {"m": RUNNING_STALE_MINUTES})).mappings().all()
        dels = (await conn.execute(text(
            "SELECT id, session_id, type, kind, posting_id, file_path FROM deliverables"
        ))).mappings().all()
        counts = {
            "users": (await conn.execute(text("SELECT count(*) FROM users"))).scalar_one(),
            "sessions": len(sessions),
            "deliverables": len(dels),
        }
        await conn.rollback()

    # 1. more than one non-abandoned active session per candidate
    per_user: dict = {}
    for s in sessions:
        if s["status"] == "active":
            per_user.setdefault(s["user_id"], []).append(s["id"])
    multi = [sid for ids in per_user.values() if len(ids) > 1 for sid in ids]
    findings["candidates_with_multiple_active_sessions"] = {
        "count": sum(1 for ids in per_user.values() if len(ids) > 1),
        "ids": _ids(multi),
    }

    # 2. invalid phase or status
    findings["invalid_phase_or_status"] = _entry(_ids(
        s["id"] for s in sessions
        if not (isinstance(s["phase"], int) and 0 <= s["phase"] <= 7)
        or s["status"] not in KNOWN_STATUSES
    ))

    # 3. completed sessions whose discovery is not complete (legacy sessions predate ids)
    findings["completed_sessions_with_incomplete_discovery"] = _entry(_ids(
        s["id"] for s in sessions
        if s["status"] in ("interview_complete", "deliverables_generated")
        and not discovery_complete_for(s["experience_level"], s["discovery_data"])
    ))

    # 4. deliverable rows whose file is missing
    findings["deliverables_with_missing_file"] = _entry(_ids(
        d["id"] for d in dels if not Path(d["file_path"]).is_file()
    ))

    # 5. duplicate deliverable rows (same session, type, kind, posting)
    groups: dict = {}
    for d in dels:
        groups.setdefault((d["session_id"], d["type"], d["kind"], d["posting_id"]), []).append(d["id"])
    dup_ids = [i for ids in groups.values() if len(ids) > 1 for i in ids]
    findings["duplicate_deliverable_rows"] = {
        "count": sum(1 for ids in groups.values() if len(ids) > 1),
        "ids": _ids(dup_ids),
    }

    # 6. files on disk with no row
    known = {str(Path(d["file_path"]).resolve()) for d in dels}
    orphans = [p for p in _files_on_disk(root) if str(p.resolve()) not in known]
    findings["files_without_row"] = {
        "count": len(orphans),
        # <session uuid>/<uuid>.<ext> in normal operation; any other name is masked (it may hold a person's name)
        "paths": sorted(_safe_rel(p, root) for p in orphans),
    }

    # 7. deliverables_generated but a required base type is missing
    have: dict = {}
    for d in dels:
        if d["kind"] != "base":
            continue
        t = d["type"]
        have.setdefault(d["session_id"], set()).update(LEGACY_SATISFIES.get(t, (LEGACY_TYPES.get(t, t),)))
    findings["generated_sessions_missing_required_types"] = _entry(_ids(
        s["id"] for s in sessions
        if s["status"] == "deliverables_generated"
        and not set(REQUIRED_BASE_TYPES) <= have.get(s["id"], set())
    ))

    # 8. generation stuck 'running'
    findings["generation_running_over_30_minutes"] = _entry(_ids(
        s["id"] for s in sessions
        if s["generation_status"] == "running" and (s["stale"] or s["generation_started_at"] is None)
    ))

    return {"totals": counts, "findings": findings}


def render_text(report: dict) -> str:
    lines = ["Resume Chat diagnostics (read-only; counts and ids only)"]
    t = report["totals"]
    lines.append(f"totals: users={t['users']} sessions={t['sessions']} deliverables={t['deliverables']}")
    for name, f in report["findings"].items():
        lines.append(f"{name}: {f['count']}")
        for item in f.get("ids", []) + f.get("paths", []):
            lines.append(f"  - {item}")
    return "\n".join(lines)


async def _main(as_json: bool) -> None:
    report = await collect()
    print(json.dumps(report, indent=2, sort_keys=True) if as_json else render_text(report))
    await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.diagnostics")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    asyncio.run(_main(args.json))
    return 0


if __name__ == "__main__":
    main()
    sys.exit(0)
