"""Stage 7 (spec J): python -m app.diagnostics against planted cases in the test DB."""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from app.database import async_session, engine
from app.diagnostics import collect
from app.models import Deliverable, Session

from .conftest import make_candidate

SECRET_NAME = "Zephyrine Quillfeather"
SECRET_ANSWER = "ZZSECRETANSWERZZ"
GOOD = {"candidate_name": SECRET_NAME, "contact": {"omitted": ["phone"]}}


async def run_cli(*args, env_extra=None):
    env = {**os.environ, **(env_extra or {})}
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "app.diagnostics", *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env, cwd="/app",
    )
    out, err = await asyncio.wait_for(proc.communicate(), 60)
    return proc.returncode, out.decode(), err.decode()


def _mk_session(user_id, **kw):
    return Session(user_id=user_id, **kw)


def _file(sdir, name, body=b"x"):
    os.makedirs(sdir, exist_ok=True)
    p = os.path.join(sdir, name)
    with open(p, "wb") as f:
        f.write(body)
    return p


async def test_diagnostics_planted_cases(client, deliverables_dir):
    c1 = await make_candidate(client, SECRET_NAME)
    c2 = await make_candidate(client, "Orlo Baskerville")
    old = datetime.now(timezone.utc) - timedelta(minutes=45)
    full_answers = {k: SECRET_ANSWER for k in
                    ("target_role", "career_narrative", "differentiator", "hidden_achievements",
                     "metrics_per_role", "leadership_influence", "skills_emphasis", "employment_gaps",
                     "certifications", "education", "context", "skills_matrix")}
    async with async_session() as db:
        dup_a = _mk_session(c1["id"], status="active", phase=2, discovery_data=GOOD)
        dup_b = _mk_session(c1["id"], status="active", phase=1, discovery_data=GOOD)
        bad_phase = _mk_session(c2["id"], status="abandoned", phase=9, discovery_data=GOOD)
        bad_status = _mk_session(c2["id"], status="weird", phase=1, discovery_data=GOOD)
        incomplete = _mk_session(c2["id"], status="interview_complete", phase=4,
                                 experience_level="experienced",
                                 discovery_data={"candidate_name": SECRET_NAME, "target_role": SECRET_ANSWER})
        complete_ok = _mk_session(c2["id"], status="abandoned", phase=3, experience_level="experienced",
                                  discovery_data={**full_answers, "contact": {"omitted": ["phone"]}})
        missing_types = _mk_session(c2["id"], status="deliverables_generated", phase=7,
                                    experience_level="experienced",
                                    discovery_data={**full_answers, "contact": {"omitted": ["phone"]}})
        legacy_ok = _mk_session(c2["id"], status="deliverables_generated", phase=7,
                                experience_level="experienced",
                                discovery_data={**full_answers, "contact": {"omitted": ["phone"]}})
        stuck = _mk_session(c2["id"], status="abandoned", phase=2, generation_status="running",
                            generation_started_at=old, discovery_data=GOOD)
        fresh = _mk_session(c2["id"], status="abandoned", phase=2, generation_status="running",
                            generation_started_at=datetime.now(timezone.utc), discovery_data=GOOD)
        db.add_all([dup_a, dup_b, bad_phase, bad_status, incomplete, complete_ok, missing_types,
                    legacy_ok, stuck, fresh])
        await db.commit()

        sdir = os.path.join(deliverables_dir, str(missing_types.id))
        present = _file(sdir, f"{uuid.uuid4()}.md", SECRET_ANSWER.encode())
        missing_row = Deliverable(session_id=missing_types.id, type="resume_md", filename=f"{SECRET_NAME}.md",
                                  file_path=os.path.join(sdir, "nope.md"))
        dup1 = Deliverable(session_id=missing_types.id, type="resume_md", filename="a.md", file_path=present)
        dup2 = Deliverable(session_id=missing_types.id, type="resume_md", filename="b.md", file_path=present)
        db.add_all([missing_row, dup1, dup2])
        for t in ("resume", "interview_prep", "skills_matrix", "score_card"):
            p = _file(os.path.join(deliverables_dir, str(legacy_ok.id)), f"{uuid.uuid4()}.bin")
            db.add(Deliverable(session_id=legacy_ok.id, type=t, filename=f"{t}.bin", file_path=p))
        await db.commit()
        orphan = _file(sdir, f"{uuid.uuid4()}.orphan")
        legacy_named = _file(sdir, f"{SECRET_NAME.replace(' ', '_')}_Resume.docx")
        _file(sdir, "discovery.md", SECRET_ANSWER.encode())      # ignored
        _file(os.path.join(sdir, ".staging", "base"), "resume.md")  # ignored
        ids = {k: str(v.id) for k, v in dict(
            dup_a=dup_a, dup_b=dup_b, bad_phase=bad_phase, bad_status=bad_status, incomplete=incomplete,
            complete_ok=complete_ok, missing_types=missing_types, legacy_ok=legacy_ok, stuck=stuck,
            fresh=fresh, missing_row=missing_row, dup1=dup1, dup2=dup2).items()}

    # in-process: the first statement is SET TRANSACTION READ ONLY
    statements: list[str] = []

    def spy(conn, cursor, statement, *a):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", spy)
    try:
        report = await collect()
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", spy)
    assert statements[0].strip().upper() == "SET TRANSACTION READ ONLY"
    f = report["findings"]
    assert {ids["dup_a"], ids["dup_b"]} <= set(f["candidates_with_multiple_active_sessions"]["ids"])
    assert {ids["bad_phase"], ids["bad_status"]} <= set(f["invalid_phase_or_status"]["ids"])
    assert ids["complete_ok"] not in f["invalid_phase_or_status"]["ids"]
    inc = f["completed_sessions_with_incomplete_discovery"]["ids"]
    assert ids["incomplete"] in inc and ids["missing_types"] not in inc and ids["legacy_ok"] not in inc
    assert ids["missing_row"] in f["deliverables_with_missing_file"]["ids"]
    assert ids["dup1"] not in f["deliverables_with_missing_file"]["ids"]
    assert {ids["dup1"], ids["dup2"]} <= set(f["duplicate_deliverable_rows"]["ids"])
    orphan_rel = os.path.relpath(orphan, deliverables_dir)
    assert orphan_rel in f["files_without_row"]["paths"]
    assert "<non-uuid-name>.docx" in "".join(p[p.rfind("/") + 1:] for p in f["files_without_row"]["paths"])
    assert not any(SECRET_NAME.split()[0] in p for p in f["files_without_row"]["paths"])
    assert not any(p.endswith("discovery.md") or ".staging" in p for p in f["files_without_row"]["paths"])
    gen = f["generated_sessions_missing_required_types"]["ids"]
    assert ids["missing_types"] in gen
    assert ids["legacy_ok"] not in gen  # legacy type names count as their modern equivalents
    run = f["generation_running_over_30_minutes"]["ids"]
    assert ids["stuck"] in run and ids["fresh"] not in run

    # CLI: exit 0, text and --json, nothing but counts and ids
    for args in ((), ("--json",)):
        rc, out, err = await run_cli(*args)
        assert rc == 0, err
        if not args:
            print("\n--- diagnostics sample (test DB) ---\n" + out)
        for forbidden in (SECRET_NAME, "Zephyrine", SECRET_ANSWER, "Orlo", "Baskerville", c1["username"]):
            assert forbidden not in out
        assert ids["dup_a"] in out and ids["stuck"] in out
        assert "files_without_row" in out
    rc, out, _ = await run_cli("--json")
    data = json.loads(out)
    assert set(data) == {"totals", "findings"} and ids["stuck"] in data["findings"][
        "generation_running_over_30_minutes"]["ids"]

    # unchanged data: it wrote nothing
    after = await collect()
    assert after["totals"] == report["totals"]


async def test_diagnostics_missing_deliverables_dir():
    rc, out, err = await run_cli("--json", env_extra={"DELIVERABLES_DIR": "/nonexistent/nowhere"})
    assert rc == 0, err
    data = json.loads(out)
    assert data["findings"]["files_without_row"] == {"count": 0, "paths": []}
