"""Stage 1 baseline.

xfail(strict=True) tests describe bugs that exist today; later stages fix them
and remove the marks. The rest pass today and must keep passing.
All candidates are synthetic.
"""

import asyncio
import glob
import os
import uuid

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.database import async_session
from app.deliverables import wait_for_generation_tasks
from app.models import Deliverable, Session

from .conftest import make_admin_headers, make_candidate


async def _make_session(user_id, **kw) -> uuid.UUID:
    async with async_session() as db:
        s = Session(user_id=user_id, **kw)
        db.add(s)
        await db.commit()
        return s.id


# ---------------------------------------------------------------- smoke


async def test_chat_send_with_fake_claude(client, fake_claude):
    nurse = await make_candidate(client, "Maria Santos RN")
    fake_claude.script("Welcome! Which role are you aiming for?")
    r = await client.post("/api/chat/send", json={"content": "Hi"}, headers=nurse["headers"])
    assert r.status_code == 200, r.text
    assert "Welcome" in r.json()["content"]
    assert len(fake_claude.calls) == 1


# ------------------------------------------------------ already works


async def test_first_visit_race_creates_one_session(client):
    hvac = await make_candidate(client, "Tom Reed HVAC")
    reqs = [
        client.get("/api/chat/session" if i % 2 else "/api/chat/messages",
                   headers=hvac["headers"])
        for i in range(12)
    ]
    results = await asyncio.gather(*reqs)
    assert all(r.status_code == 200 for r in results)
    async with async_session() as db:
        n = (await db.execute(
            select(func.count()).select_from(Session).where(Session.user_id == hvac["id"])
        )).scalar_one()
    assert n == 1


async def test_candidate_cannot_download_other_candidates_deliverable(client, deliverables_dir):
    a = await make_candidate(client, "Alice Sales")
    b = await make_candidate(client, "Bob Logistics")
    sid = await _make_session(b["id"])
    d = os.path.join(deliverables_dir, str(sid))
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "Bob_Resume_FINAL.md")
    with open(path, "w") as f:
        f.write("# Bob\n")
    async with async_session() as db:
        dv = Deliverable(session_id=sid, type="resume_md", filename="Bob_Resume_FINAL.md",
                         file_path=path)
        db.add(dv)
        await db.commit()
        did = dv.id

    assert (await client.get(f"/api/deliverables/{did}/download", headers=a["headers"])).status_code == 403
    assert (await client.get(f"/api/deliverables/{did}/preview", headers=a["headers"])).status_code == 403
    assert (await client.get(f"/api/deliverables/{did}/download", headers=b["headers"])).status_code == 200


async def test_candidate_cannot_call_admin_routes(client):
    c = await make_candidate(client, "Dana Teacher")
    h = c["headers"]
    assert (await client.get("/api/admin/candidates", headers=h)).status_code == 403
    assert (await client.post("/api/admin/candidates",
                              json={"name": "X Y", "password": "p"}, headers=h)).status_code == 403
    assert (await client.get("/api/admin/profiles", headers=h)).status_code == 403
    sid = uuid.uuid4()
    assert (await client.post(f"/api/deliverables/generate?session_id={sid}", headers=h)).status_code == 403


# ------------------------------------------------- known bugs (xfail)


async def test_filename_traversal_stays_in_session_dir(client, admin_headers, fake_claude, deliverables_dir):
    c = await make_candidate(client, "Eve Nonprofit")
    marker = f"escape_{uuid.uuid4().hex[:8]}"
    # <DELIVERABLES_DIR>/<sid>/../../<marker>_... lands in the parent of DELIVERABLES_DIR
    sid = await _make_session(
        c["id"], discovery_data={"candidate_name": f"../../{marker}"}, phase=3,
        status="interview_complete",
    )
    fake_claude.script("# R", "# P", "<html></html>", "# S")
    escaped = os.path.join(os.path.dirname(deliverables_dir), f"{marker}*")
    try:
        r = await client.post(f"/api/deliverables/generate?session_id={sid}", headers=admin_headers)
        assert r.status_code == 202
        await wait_for_generation_tasks()
        assert glob.glob(escaped) == [], "files were written outside the session dir"
    finally:
        for p in glob.glob(escaped):
            os.remove(p)


async def test_pandoc_failure_does_not_register_docx(client, admin_headers, fake_claude, monkeypatch, tmp_path):
    c = await make_candidate(client, "Frank Software")
    sid = await _make_session(c["id"], discovery_data={"candidate_name": "Frank Software"},
                              phase=3, status="interview_complete")
    fake_claude.script("# R", "# P", "<html></html>", "# S")
    monkeypatch.setenv("PATH", str(tmp_path))  # empty dir: pandoc is missing
    r = await client.post(f"/api/deliverables/generate?session_id={sid}", headers=admin_headers)
    assert r.status_code == 202
    await wait_for_generation_tasks()
    async with async_session() as db:
        rows = (await db.execute(
            select(Deliverable).where(Deliverable.session_id == sid)
        )).scalars().all()
        s = (await db.execute(select(Session).where(Session.id == sid))).scalar_one()
    assert rows == []
    assert s.generation_status == "failed"


@pytest.mark.xfail(strict=True, reason="META from the model is applied unvalidated (phase 99, status deliverables_generated)")
async def test_meta_phase_and_status_are_validated(client, fake_claude):
    c = await make_candidate(client, "Gina Marketing")
    fake_claude.script('Sure.<!--META:{"phase": 99, "status": "deliverables_generated"}-->')
    r = await client.post("/api/chat/send", json={"content": "hello"}, headers=c["headers"])
    assert r.status_code == 200, r.text
    s = (await client.get("/api/chat/session", headers=c["headers"])).json()
    assert s["phase"] <= 3
    assert s["status"] == "active"


@pytest.mark.xfail(strict=True, reason="new-session has no lock or idempotency: concurrent calls each create a session instead of one replacing the current one")
async def test_concurrent_new_session_creates_exactly_one(client):
    c = await make_candidate(client, "Hank Nursing")
    old = (await client.get("/api/chat/session", headers=c["headers"])).json()["id"]
    rs = await asyncio.gather(*[
        client.post("/api/chat/new-session", json={"replaces_session_id": old},
                    headers=c["headers"]) for _ in range(8)
    ])
    assert all(r.status_code == 200 for r in rs)
    async with async_session() as db:
        rows = (await db.execute(
            select(Session.status).where(Session.user_id == c["id"])
        )).scalars().all()
    # one abandoned original + exactly one new active session
    assert sorted(rows) == ["abandoned", "active"]


@pytest.mark.xfail(strict=True, reason="HTML previews are returned with no sandbox CSP (frontend half is Stage 6)")
async def test_html_preview_has_sandbox_csp(client, deliverables_dir):
    c = await make_candidate(client, "Ivy Teaching")
    sid = await _make_session(c["id"])
    d = os.path.join(deliverables_dir, str(sid))
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "Ivy_Skills_Matrix.html")
    with open(path, "w") as f:
        f.write("<html><script>alert(1)</script></html>")
    async with async_session() as db:
        dv = Deliverable(session_id=sid, type="skills_matrix_html",
                         filename="Ivy_Skills_Matrix.html", file_path=path)
        db.add(dv)
        await db.commit()
        did = dv.id
    r = await client.get(f"/api/deliverables/{did}/preview", headers=c["headers"])
    assert r.status_code == 200
    assert "sandbox" in r.headers.get("content-security-policy", "")


@pytest.mark.xfail(strict=True, reason="resume upload has no size limit; a ~6 MB body is accepted into memory (plan says 50 MB; 6 MB proves the same)")
async def test_oversized_upload_rejected(client):
    c = await make_candidate(client, "Jon Logistics")
    payload = b"experience line\n" * (6 * 1024 * 1024 // 16)  # ~6 MB, in memory
    r = await client.post(
        "/api/chat/resume",
        files={"file": ("resume.txt", payload, "text/plain")},
        headers=c["headers"],
    )
    assert r.status_code == 413
