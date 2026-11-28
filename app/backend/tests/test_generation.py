"""Stage 2: filesystem safety and the document-generation contract. Synthetic people only."""

import asyncio
import os
import subprocess
import types
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from docx import Document
from sqlalchemy import select, update

from app.config import settings
from app.database import async_session
from app.deliverables import wait_for_generation_tasks
from app.models import Deliverable, Posting, Session
from app.storage import download_name, resolve_inside, safe_component, storage_name

from .conftest import make_candidate

BASE_REPLIES = ("# {name}\n\nSummary line.", "# Prep", "<html><body>matrix</body></html>", "# Score")


async def _session(client, name, data_name=None):
    c = await make_candidate(client, name)
    async with async_session() as db:
        s = Session(user_id=c["id"], phase=3, status="interview_complete",
                    discovery_data={"candidate_name": data_name or name})
        db.add(s)
        await db.commit()
        return c, s.id


async def _rows(sid, kind=None):
    async with async_session() as db:
        q = select(Deliverable).where(Deliverable.session_id == sid)
        if kind:
            q = q.where(Deliverable.kind == kind)
        return (await db.execute(q)).scalars().all()


async def _sess(sid) -> Session:
    async with async_session() as db:
        return (await db.execute(select(Session).where(Session.id == sid))).scalar_one()


async def _generate(client, admin_headers, sid):
    r = await client.post(f"/api/deliverables/generate?session_id={sid}", headers=admin_headers)
    assert r.status_code == 202, r.text
    await wait_for_generation_tasks()


def _script_base(fake, name="Maria Santos"):
    fake.script(BASE_REPLIES[0].format(name=name), *BASE_REPLIES[1:])


# ------------------------------------------------------------------ names


@pytest.mark.parametrize("raw,expected", [
    ("Maria Santos", "Maria_Santos"),
    ("José Ñúñez-O'Brien", "José_Ñúñez-OBrien"),
    ("李小龙", "李小龙"),
    ("../../etc/passwd", "etcpasswd"),
    ("/abs/path", "abspath"),
    ("C:\\x", "Cx"),
    ("", "FB"),
    ("   ", "FB"),
    ("a\x00b\nc", "abc"),
])
def test_safe_component(raw, expected):
    out = safe_component(raw, "FB")
    assert out == expected
    assert "/" not in out and "\\" not in out and ".." not in out and not out.startswith(".")


def test_safe_component_length_and_download_name():
    assert len(safe_component("x" * 500, "FB")) == 60
    assert len(safe_component("李" * 500, "FB")) == 60
    n = download_name("x" * 500, "Resume", ".docx", "c" * 500, "r" * 500)
    assert len(n) <= 120 and n.endswith(".docx")
    assert download_name("José Núñez", "Resume_FINAL", "docx") == "José_Núñez_Resume_FINAL.docx"


def test_resolve_inside_and_storage_name(tmp_path):
    base = tmp_path / "b"
    base.mkdir()
    assert resolve_inside(base, "x.md") == (base / "x.md").resolve()
    for bad in ("../x", "/etc/passwd", "a/../../x"):
        with pytest.raises(ValueError):
            resolve_inside(base, bad)
    did = uuid.uuid4()
    assert storage_name(did, "docx") == f"{did}.docx"


# -------------------------------------------------- download route safety


async def _row_with_path(sid, path, dtype="resume_md", filename="x.md"):
    async with async_session() as db:
        dv = Deliverable(session_id=sid, type=dtype, filename=filename, file_path=path)
        db.add(dv)
        await db.commit()
        return dv.id


async def test_download_refuses_paths_outside_dir(client, deliverables_dir, tmp_path):
    c, sid = await _session(client, "Gil Teacher")
    secret = tmp_path / "secret.md"
    secret.write_text("secret")
    sdir = os.path.join(deliverables_dir, str(sid))
    os.makedirs(sdir, exist_ok=True)
    os.symlink(secret, os.path.join(sdir, "link.md"))
    for bad in (str(secret), "/etc/passwd", f"{sdir}/../../../etc/passwd", os.path.join(sdir, "link.md")):
        did = await _row_with_path(sid, bad)
        for route in ("download", "preview"):
            r = await client.get(f"/api/deliverables/{did}/{route}", headers=c["headers"])
            assert r.status_code == 404, (bad, route)
            assert str(secret) not in r.text and "etc/passwd" not in r.text


async def test_legacy_row_still_downloads_and_no_path_leaks(client, deliverables_dir):
    c, sid = await _session(client, "Hal Nonprofit")
    sdir = os.path.join(deliverables_dir, str(sid))
    os.makedirs(sdir, exist_ok=True)
    path = os.path.join(sdir, "Hal_Nonprofit_Resume_FINAL.md")
    open(path, "w").write("# Hal\n")
    did = await _row_with_path(sid, path, "resume", "Hal_Nonprofit_Resume_FINAL.md")
    r = await client.get(f"/api/deliverables/{did}/download", headers=c["headers"])
    assert r.status_code == 200 and r.content == b"# Hal\n"
    assert 'filename="Hal_Nonprofit_Resume_FINAL.md"' in r.headers["content-disposition"]
    r = await client.get(f"/api/deliverables/{did}/preview", headers=c["headers"])
    assert r.status_code == 200 and "file_path" not in r.text and path not in r.text
    r = await client.get("/api/deliverables", headers=c["headers"])
    assert "file_path" not in r.text and path not in r.text


async def test_unicode_download_filename_uses_rfc5987(client, deliverables_dir):
    c, sid = await _session(client, "Ivo Logistics")
    sdir = os.path.join(deliverables_dir, str(sid))
    os.makedirs(sdir, exist_ok=True)
    path = os.path.join(sdir, f"{uuid.uuid4()}.md")
    open(path, "w").write("x")
    did = await _row_with_path(sid, path, filename="李小龙_Resume_FINAL.md")
    r = await client.get(f"/api/deliverables/{did}/download", headers=c["headers"])
    assert r.status_code == 200
    assert "filename*=UTF-8''" in r.headers["content-disposition"]
    assert "%E6%9D%8E" in r.headers["content-disposition"]


# ------------------------------------------------------------- generation


async def test_generate_success(client, admin_headers, fake_claude):
    c, sid = await _session(client, "José Ñúñez-O'Brien")
    _script_base(fake_claude, "José Ñúñez-O'Brien")
    await _generate(client, admin_headers, sid)
    s = await _sess(sid)
    assert s.generation_status == "done" and s.generation_error is None
    assert s.status == "deliverables_generated"
    rows = await _rows(sid)
    assert sorted(r.type for r in rows) == sorted(
        ["resume_md", "resume_docx", "interview_prep_md", "skills_matrix_html", "score_card_md"])
    assert all(r.kind == "base" and r.posting_id is None for r in rows)
    sdir = os.path.join(settings.DELIVERABLES_DIR, str(sid))
    for r in rows:
        assert os.path.basename(r.file_path).startswith(str(r.id))
        assert os.path.getsize(r.file_path) > 0
        assert os.path.dirname(r.file_path) == sdir
    assert not os.path.exists(os.path.join(sdir, ".staging", "base"))
    docx_row = next(r for r in rows if r.type == "resume_docx")
    assert docx_row.filename == "José_Ñúñez-OBrien_Resume_FINAL.docx"
    text = "\n".join(p.text for p in Document(docx_row.file_path).paragraphs)
    assert "Ñúñez" in text
    # the download works and no listing leaks paths
    r = await client.get(f"/api/deliverables/{docx_row.id}/download", headers=c["headers"])
    assert r.status_code == 200
    r = await client.get("/api/deliverables", headers=admin_headers)
    assert "file_path" not in r.text and settings.DELIVERABLES_DIR not in r.text


async def test_traversal_name_and_same_names_do_not_collide(client, admin_headers, fake_claude):
    c1, s1 = await _session(client, "Twin Sales", "../../etc/passwd")
    c2, s2 = await _session(client, "Twin Sales", "../../etc/passwd")
    for sid in (s1, s2):
        _script_base(fake_claude, "Twin")
        await _generate(client, admin_headers, sid)
    for sid in (s1, s2):
        rows = await _rows(sid)
        assert len(rows) == 5
        assert all(r.filename.startswith("etcpasswd_") for r in rows)
        assert all(os.path.dirname(r.file_path).endswith(str(sid)) for r in rows)


async def _failed(sid, contains):
    s = await _sess(sid)
    assert s.generation_status == "failed"
    assert contains in s.generation_error
    assert "Traceback" not in s.generation_error and "/" not in s.generation_error
    assert await _rows(sid) == []


async def test_pandoc_missing(client, admin_headers, fake_claude, monkeypatch, tmp_path):
    c, sid = await _session(client, "Ned HVAC")
    _script_base(fake_claude)
    monkeypatch.setenv("PATH", str(tmp_path))
    await _generate(client, admin_headers, sid)
    await _failed(sid, "pandoc is not installed")


async def test_template_missing(client, admin_headers, fake_claude, monkeypatch, tmp_path):
    c, sid = await _session(client, "Opal Nursing")
    _script_base(fake_claude)
    monkeypatch.setattr(settings, "TEMPLATES_DIR", str(tmp_path))
    await _generate(client, admin_headers, sid)
    await _failed(sid, "template is missing")


async def test_pandoc_timeout_and_error(client, admin_headers, fake_claude, monkeypatch):
    import app.deliverables as d

    for exc, msg in ((subprocess.TimeoutExpired("pandoc", 30), "too long"),
                     (subprocess.CalledProcessError(1, "pandoc", stderr=b"SECRET stderr"), "Word conversion failed")):
        c, sid = await _session(client, "Pam Marketing")
        _script_base(fake_claude)

        def boom(*a, _exc=exc, **k):
            raise _exc

        monkeypatch.setattr(d, "subprocess", types.SimpleNamespace(
            run=boom, TimeoutExpired=subprocess.TimeoutExpired,
            CalledProcessError=subprocess.CalledProcessError))
        await _generate(client, admin_headers, sid)
        await _failed(sid, msg)
        assert "SECRET" not in (await _sess(sid)).generation_error


async def test_empty_resume_fails(client, admin_headers, fake_claude):
    c, sid = await _session(client, "Quin Software")
    fake_claude.script("   ")
    await _generate(client, admin_headers, sid)
    await _failed(sid, "came back empty")


async def test_partial_failure_keeps_previous_set(client, admin_headers, fake_claude):
    c, sid = await _session(client, "Rae Teaching")
    _script_base(fake_claude, "Rae Teaching")
    await _generate(client, admin_headers, sid)
    before = {r.id: r.file_path for r in await _rows(sid)}
    assert len(before) == 5

    fake_claude.script("# New resume", "# New prep", RuntimeError("boom with /secret/path"))
    await _generate(client, admin_headers, sid)
    s = await _sess(sid)
    assert s.generation_status == "failed" and s.status == "deliverables_generated"
    assert "secret" not in s.generation_error and "boom" not in s.generation_error
    after = {r.id: r.file_path for r in await _rows(sid)}
    assert after == before
    assert all(os.path.exists(p) for p in before.values())


async def test_retry_reuses_staged_text(client, admin_headers, fake_claude):
    c, sid = await _session(client, "Sol Logistics")
    fake_claude.script("# Sol resume", "# Sol prep", RuntimeError("transient"))
    await _generate(client, admin_headers, sid)
    assert (await _sess(sid)).generation_status == "failed"
    assert len(fake_claude.calls) == 3
    fake_claude.script("<html>m</html>", "# Score")
    await _generate(client, admin_headers, sid)
    assert len(fake_claude.calls) == 5  # resume and prep were not regenerated
    s = await _sess(sid)
    assert s.generation_status == "done" and s.generation_error is None
    assert len(await _rows(sid)) == 5


async def test_regeneration_replaces_rows_and_files(client, admin_headers, fake_claude):
    c, sid = await _session(client, "Tia Nonprofit")
    _script_base(fake_claude, "Tia Nonprofit")
    await _generate(client, admin_headers, sid)
    old = await _rows(sid)
    _script_base(fake_claude, "Tia Nonprofit")
    await _generate(client, admin_headers, sid)
    new = await _rows(sid)
    assert len(new) == 5
    assert not ({r.id for r in old} & {r.id for r in new})
    assert not any(os.path.exists(r.file_path) for r in old)
    assert all(os.path.exists(r.file_path) for r in new)


async def test_legacy_rows_replaced_on_generate(client, admin_headers, fake_claude, deliverables_dir):
    c, sid = await _session(client, "Uma Sales")
    sdir = os.path.join(deliverables_dir, str(sid))
    os.makedirs(sdir, exist_ok=True)
    legacy = os.path.join(sdir, "Uma_Sales_Resume_FINAL.md")
    open(legacy, "w").write("old")
    await _row_with_path(sid, legacy, "resume", "Uma_Sales_Resume_FINAL.md")
    _script_base(fake_claude, "Uma Sales")
    await _generate(client, admin_headers, sid)
    assert len(await _rows(sid)) == 5
    assert not os.path.exists(legacy)


async def test_regeneration_keeps_legacy_targeted_rows_with_default_kind(
    client, admin_headers, fake_claude, deliverables_dir
):
    """A pre-migration targeted row carries the column default kind='base'; it must survive."""
    c, sid = await _session(client, "Una Hvac")
    sdir = os.path.join(deliverables_dir, str(sid))
    os.makedirs(sdir, exist_ok=True)
    tgt = os.path.join(sdir, "Una_Hvac_Resume_Acme_Tech.docx")
    open(tgt, "w").write("targeted")
    await _row_with_path(sid, tgt, "resume_targeted_docx", "Una_Hvac_Resume_Acme_Tech.docx")
    async with async_session() as db:  # default kind is 'base'
        assert (await db.execute(select(Deliverable.kind).where(Deliverable.session_id == sid))).scalar_one() == "base"
    _script_base(fake_claude, "Una Hvac")
    await _generate(client, admin_headers, sid)
    types = sorted(r.type for r in await _rows(sid))
    assert "resume_targeted_docx" in types and len(types) == 6
    assert os.path.exists(tgt)


async def test_simultaneous_generate_one_202_one_409(client, admin_headers, fake_claude):
    c, sid = await _session(client, "Vic HVAC")
    fake_claude.script(("sleep", 1, "# Vic resume"), "# prep", "<html>m</html>", "# score")
    rs = await asyncio.gather(*[
        client.post(f"/api/deliverables/generate?session_id={sid}", headers=admin_headers)
        for _ in range(2)
    ])
    assert sorted(r.status_code for r in rs) == [202, 409]
    assert "already being generated" in next(r for r in rs if r.status_code == 409).json()["detail"]
    lst = await client.get("/api/admin/candidates", headers=admin_headers)
    mine = next(x for x in lst.json() if x["id"] == str(c["id"]))
    assert mine["generation_status"] == "running"
    await wait_for_generation_tasks()
    assert (await _sess(sid)).generation_status == "done"
    assert len(await _rows(sid)) == 5


async def test_stale_running_claim_can_be_retaken(client, admin_headers, fake_claude):
    c, sid = await _session(client, "Wes Marketing")
    async with async_session() as db:
        await db.execute(update(Session).where(Session.id == sid).values(
            generation_status="running",
            generation_started_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
        await db.commit()
    r = await client.post(f"/api/deliverables/generate?session_id={sid}", headers=admin_headers)
    assert r.status_code == 409
    async with async_session() as db:
        await db.execute(update(Session).where(Session.id == sid).values(
            generation_started_at=datetime.now(timezone.utc) - timedelta(minutes=31)))
        await db.commit()
    _script_base(fake_claude, "Wes Marketing")
    await _generate(client, admin_headers, sid)
    assert (await _sess(sid)).generation_status == "done"


async def test_interrupted_run_becomes_failed_in_admin_list(client, admin_headers, fake_claude):
    """A run orphaned by a restart surfaces as failed (Try again) once the claim is stale."""
    c, sid = await _session(client, "Ivy Interrupted")
    async with async_session() as db:
        await db.execute(update(Session).where(Session.id == sid).values(
            generation_status="running",
            generation_started_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
        await db.commit()
    lst = (await client.get("/api/admin/candidates", headers=admin_headers)).json()
    assert next(x for x in lst if x["id"] == str(c["id"]))["generation_status"] == "running"
    async with async_session() as db:
        await db.execute(update(Session).where(Session.id == sid).values(
            generation_started_at=datetime.now(timezone.utc) - timedelta(minutes=31)))
        await db.commit()
    lst = (await client.get("/api/admin/candidates", headers=admin_headers)).json()
    mine = next(x for x in lst if x["id"] == str(c["id"]))
    assert mine["generation_status"] == "failed" and "interrupted" in mine["generation_error"]
    _script_base(fake_claude, "Ivy Interrupted")
    await _generate(client, admin_headers, sid)
    assert (await _sess(sid)).generation_status == "done"


async def test_failed_status_visible_in_admin_list(client, admin_headers, fake_claude):
    c, sid = await _session(client, "Xan Software")
    fake_claude.script("")
    await _generate(client, admin_headers, sid)
    lst = (await client.get("/api/admin/candidates", headers=admin_headers)).json()
    mine = next(x for x in lst if x["id"] == str(c["id"]))
    assert mine["generation_status"] == "failed" and "empty" in mine["generation_error"]


# --------------------------------------------------------------- targeted


async def _target(client, admin_headers, sid, company, role, cover=False):
    r = await client.post("/api/deliverables/target", headers=admin_headers, json={
        "session_id": str(sid), "company": company, "role": role,
        "posting_text": f"{role} at {company}", "include_cover_letter": cover})
    assert r.status_code == 202, r.text
    await wait_for_generation_tasks()


async def test_targeted_variants_for_two_postings_survive(client, admin_headers, fake_claude):
    c, sid = await _session(client, "Yara Nursing")
    fake_claude.script("# BASEMARK resume", "# prep", "<html>m</html>", "# score")
    await _generate(client, admin_headers, sid)
    base_ids = {r.id for r in await _rows(sid, "base")}

    fake_claude.script("# T1 resume", "# T1 cover")
    await _target(client, admin_headers, sid, "Acme Health", "Charge Nurse", cover=True)
    assert "BASEMARK" in fake_claude.calls[-2]["messages"][0]["content"]
    fake_claude.script("# T2 resume")
    await _target(client, admin_headers, sid, "Acme Health", "Charge Nurse")

    targeted = await _rows(sid, "targeted")
    assert len(targeted) == 6  # 4 + 2
    assert len({r.posting_id for r in targeted}) == 2 and None not in {r.posting_id for r in targeted}
    assert {r.id for r in await _rows(sid, "base")} == base_ids
    assert all(os.path.exists(r.file_path) for r in await _rows(sid))
    assert (await _sess(sid)).generation_status == "done"
    assert (await _sess(sid)).status == "deliverables_generated"
    async with async_session() as db:
        assert len((await db.execute(select(Posting).where(Posting.session_id == sid))).scalars().all()) == 2


async def test_targeted_failure_leaves_nothing_and_second_call_409s_while_running(client, admin_headers, fake_claude):
    c, sid = await _session(client, "Zed Logistics")
    fake_claude.script(("sleep", 1, "# T resume"))
    r1 = client.post("/api/deliverables/target", headers=admin_headers, json={
        "session_id": str(sid), "company": "Co", "role": "Dispatcher", "posting_text": "x"})
    r2 = client.post("/api/deliverables/target", headers=admin_headers, json={
        "session_id": str(sid), "company": "Co2", "role": "Dispatcher", "posting_text": "x"})
    rs = await asyncio.gather(r1, r2)
    assert sorted(r.status_code for r in rs) == [202, 409]
    await wait_for_generation_tasks()
    # pandoc/template fine, so the one run succeeded; only one posting was recorded
    async with async_session() as db:
        assert len((await db.execute(select(Posting).where(Posting.session_id == sid))).scalars().all()) == 1


async def test_targeted_retry_reuses_staged_text_and_posting(client, admin_headers, fake_claude):
    from app.claude_client import ClaudeUnavailable

    c, sid = await _session(client, "Tess Marketing")
    fake_claude.script("# T resume STAGED", ClaudeUnavailable("down"))
    r = await client.post("/api/deliverables/target", headers=admin_headers, json={
        "session_id": str(sid), "company": "Acme", "role": "Brand Lead",
        "posting_text": "Brand Lead at Acme", "include_cover_letter": True})
    assert r.status_code == 202
    await wait_for_generation_tasks()
    s = await _sess(sid)
    assert s.generation_status == "failed" and s.generation_kind == "targeted"
    pid = s.generation_posting_id
    assert pid is not None and await _rows(sid) == []
    listed = [x for x in (await client.get("/api/admin/candidates", headers=admin_headers)).json()
              if x["session_id"] == str(sid)][0]
    assert listed["generation_kind"] == "targeted" and listed["generation_posting_id"] == str(pid)
    assert len(fake_claude.calls) == 2

    fake_claude.script("# cover letter")
    r = await client.post(f"/api/deliverables/target/{pid}/retry", headers=admin_headers)
    assert r.status_code == 202, r.text
    await wait_for_generation_tasks()
    assert len(fake_claude.calls) == 3  # only the cover letter was generated again
    assert (await _sess(sid)).generation_status == "done"
    types = sorted(x.type for x in await _rows(sid, "targeted"))
    assert types == ["cover_letter_docx", "cover_letter_md", "resume_targeted_docx", "resume_targeted_md"]
    async with async_session() as db:
        assert len((await db.execute(select(Posting).where(Posting.session_id == sid))).scalars().all()) == 1
    r = await client.post(f"/api/deliverables/target/{uuid.uuid4()}/retry", headers=admin_headers)
    assert r.status_code == 404


async def test_base_generation_records_kind_base(client, admin_headers, fake_claude):
    c, sid = await _session(client, "Bo Base")
    _script_base(fake_claude, "Bo Base")
    await _generate(client, admin_headers, sid)
    s = await _sess(sid)
    assert s.generation_kind == "base" and s.generation_posting_id is None


async def test_commit_for_deleted_session_fails_quietly_without_recreating_directory(
    client, deliverables_dir, tmp_path
):
    from app.deliverables import DocumentError, _commit_set, _guarded
    from app.storage import session_dir

    ghost = uuid.uuid4()
    staged = tmp_path / "resume.md"
    staged.write_text("# x")
    items = [dict(type="resume_md", ext=".md", staged=staged, filename="x.md")]
    with pytest.raises(DocumentError):
        await _commit_set(ghost, items, kind="base", posting_id=None,
                          replace_base=True, mark_generated=True)
    assert not os.path.exists(session_dir(ghost))

    async def work():  # a run that recreated the directory, then the session is found gone
        os.makedirs(session_dir(ghost), exist_ok=True)
        raise DocumentError("boom")

    await _guarded(ghost, work())  # no exception
    assert not os.path.exists(session_dir(ghost))


# --------------------------------------------------------- profile slugs


async def test_profile_generate_slug_rules(client, admin_headers, fake_claude, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "PROFILES_DIR", str(tmp_path))
    r = await client.post("/api/admin/profiles/generate", headers=admin_headers,
                          json={"role_name": "!!!"})
    assert r.status_code == 422
    (tmp_path / "hvac_tech.md").write_text("# Profile: existing\n")
    r = await client.post("/api/admin/profiles/generate", headers=admin_headers,
                          json={"role_name": "HVAC Tech"})
    assert r.status_code == 409
    assert (tmp_path / "hvac_tech.md").read_text() == "# Profile: existing\n"
    fake_claude.script("# Profile: Dental Hygienist\n\nbody")
    r = await client.post("/api/admin/profiles/generate", headers=admin_headers,
                          json={"role_name": "../../Dental Hygienist"})
    assert r.status_code == 200, r.text
    assert (tmp_path / "dental_hygienist.md").exists()
