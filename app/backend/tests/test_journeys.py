"""Stage 5: scripted interview journeys and the candidate fact snapshot.

A fake interviewer replies with META (and RESUME in phase 3). Assertions are on
backend state, the prompts the backend builds, the snapshot and the documents, not on
model prose. Synthetic people only.
"""

import json
import os
import re
import uuid

import pytest
from docx import Document
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.deliverables import build_fact_snapshot, wait_for_generation_tasks
from app.interview import (
    EARLY_CAREER_QUESTION_IDS,
    EXPERIENCED_QUESTION_IDS,
    discovery_complete,
    progress,
)
from app.models import Deliverable, Message, Session
from app.prompts import build_system_prompt, get_available_profiles, reload_system_files
from app.session_state import extract_resume

from .conftest import make_candidate, sdk_timeout

SEND = "/api/chat/send"
CONTACT_MARK = "CONTACT DETAILS FIRST"
PREP, MATRIX, SCORE = (
    "# Interview Prep\n\nPrepare a story about a hard shift.",
    "<html><body><table><tr><td>Skill</td></tr></table></body></html>",
    "# Score Card\n\nClear layout.",
)


def meta(**kw) -> str:
    return f"<!--META:{json.dumps(kw)}-->"


async def load(sid) -> Session:
    async with async_session() as db:
        return (await db.execute(select(Session).where(Session.id == uuid.UUID(str(sid))))).scalar_one()


async def prompt_for(sid) -> str:
    return build_system_prompt(await load(sid))


async def current_sid(client, c) -> str:
    return (await client.get("/api/chat/session", headers=c["headers"])).json()["id"]


async def turn(client, fake, c, sid, reply, content="my answer"):
    """One chat turn. Returns (response_json, system_prompt_the_model_saw)."""
    seen = {}

    def cb(kw):
        seen["system"] = kw["system"]
        return reply

    fake.script(cb)
    r = await client.post(
        SEND,
        json={"content": content, "session_id": sid, "client_message_id": str(uuid.uuid4())},
        headers=c["headers"],
    )
    assert r.status_code == 200, r.text
    return r.json(), seen["system"]


def resume_md(name, contact_line, role="Operations"):
    return (
        f"# {name}\n\n{contact_line}\n\n## Summary\n{role} professional with a record of steady results.\n\n"
        f"## Experience\n**Lead**, Riverbend Group\n\n- Trained a team of 12 people\n"
        f"- Cut average turnaround by about 20%\n\n## Education\nBS, State University\n"
    )


def visible(md: str) -> set[str]:
    out = set()
    for ln in md.splitlines():
        ln = re.sub(r"^\s*(#+|[-*+])\s+", "", ln).replace("**", "").replace("__", "")
        ln = " ".join(ln.split())
        if ln:
            out.add(ln)
    return out


def docx_lines(path) -> set[str]:
    d = Document(path)
    out = set()
    for p in d.paragraphs:
        t = " ".join(p.text.replace("’", "'").split())
        if t:
            out.add(t)
    return out


async def run_interview(client, fake, c, *, level, name, contact, answers, resume, upload=None,
                        skip=(), model_profile=True, profile=None):
    """Drive a whole interview with a scripted interviewer. Returns the session id."""
    ids = EARLY_CAREER_QUESTION_IDS if level == "early_career" else EXPERIENCED_QUESTION_IDS
    sid = await current_sid(client, c)
    slug = profile or get_available_profiles()[0]
    if upload:
        r = await client.post("/api/chat/resume", files={"file": ("resume.txt", upload.encode(), "text/plain")},
                              headers=c["headers"])
        assert r.status_code == 200
    # phase 0 -> 1: profile
    if model_profile:
        await turn(client, fake, c, sid, "Which field?" + meta(profile_slug=slug, phase=1))
    else:
        r = await client.patch("/api/chat/profile", json={"profile_slug": slug}, headers=c["headers"])
        assert r.json()["phase"] == 1
    s = await load(sid)
    assert (s.phase, s.profile_slug) == (1, slug)
    # phase 1: upload note and contact instruction
    _, system = await turn(client, fake, c, sid, "Is this contact info current?")
    assert CONTACT_MARK in system and "`omitted`" in system
    assert ("<candidate_document>" in system) == bool(upload)
    assert ("No Resume Uploaded" in system) == (not upload)
    # confirm contact, detect level -> phase 2
    await turn(client, fake, c, sid, "Thanks, saved." + meta(
        experience_level=level, phase=2,
        discovery_update={"candidate_name": name, "contact": contact}))
    s = await load(sid)
    assert s.phase == 2 and s.experience_level == level and s.discovery_data["contact"] == contact
    # discovery, one id at a time
    for i, qid in enumerate(ids, start=1):
        system = await prompt_for(sid)
        done = len(progress(await load(sid))[0]) + len(progress(await load(sid))[1])
        assert f"question {done + 1} of {len(ids)} (id `{qid}`)" in system, qid
        assert CONTACT_MARK not in system
        last = i == len(ids)
        if qid in skip:
            prev = list(progress(await load(sid))[1])
            upd = {"skipped_questions": prev + [qid]}
        else:
            upd = {qid: answers[qid]}
        await turn(client, fake, c, sid, "Noted." + meta(discovery_update=upd, **({"phase": 3} if last else {})))
    s = await load(sid)
    assert s.phase == 3 and discovery_complete(s)
    # phase 3: present the resume, then approval
    system = await prompt_for(sid)
    assert "<!--RESUME-->" in system
    shown, _ = await turn(client, fake, c, sid, f"Here is your resume.\n<!--RESUME-->\n{resume}\n<!--/RESUME-->\nAny changes?")
    assert "RESUME" not in shown["content"] and resume.splitlines()[0] in shown["content"]
    s = await load(sid)
    assert s.resume_draft == resume.strip() and s.status == "active" and s.approved_resume is None
    await turn(client, fake, c, sid, "Wonderful." + meta(status="interview_complete"))
    s = await load(sid)
    assert s.status == "interview_complete" and s.approved_resume == s.resume_draft == resume.strip()
    return sid


async def generate(client, admin_headers, fake, sid, replies=(PREP, MATRIX, SCORE)):
    n = len(fake.calls)
    fake.script(*replies)
    r = await client.post(f"/api/deliverables/generate?session_id={sid}", headers=admin_headers)
    assert r.status_code == 202, r.text
    await wait_for_generation_tasks()
    return fake.calls[n:]


async def rows(sid):
    async with async_session() as db:
        return (await db.execute(select(Deliverable).where(Deliverable.session_id == sid))).scalars().all()


def answers_for(ids, tag):
    return {q: f"{tag}: answer for {q}" for q in ids}


# -------------------------------------------------------------- scenario 1


async def test_s1_experienced_with_upload(client, fake_claude, admin_headers):
    c = await make_candidate(client, "Rosa Delgado")
    contact = {"location": "Houston, TX", "phone": "713-555-0142", "email": "rosa.delgado@example.test"}
    resume = resume_md("Rosa Delgado, RN", "Houston, TX / rosa.delgado@example.test / 713-555-0142", "ICU nursing")
    sid = await run_interview(
        client, fake_claude, c, level="experienced", name="Rosa Delgado", contact=contact,
        answers=answers_for(EXPERIENCED_QUESTION_IDS, "icu"), resume=resume,
        upload="Rosa Delgado ICU nurse ZZUPLOADTOKEN rosa.old@example.test 281-555-0100")
    calls = await generate(client, admin_headers, fake_claude, sid)
    assert len(calls) == 3  # no Claude call for the resume
    # the original upload never reaches any document prompt when a resume is approved
    for call in calls:
        blob = call["system"] + json.dumps(call["messages"])
        assert "ZZUPLOADTOKEN" not in blob and "rosa.old@example.test" not in blob
        assert "Candidate's original resume" not in blob
    rs = {r.type: r for r in await rows(sid)}
    assert set(rs) == {"resume_md", "resume_docx", "interview_prep_md", "skills_matrix_html", "score_card_md"}
    md = open(rs["resume_md"].file_path, encoding="utf-8").read()
    assert md.strip() == resume.strip()
    assert docx_lines(rs["resume_docx"].file_path) == visible(md)


# -------------------------------------------------------------- scenario 2


async def test_s2_experienced_without_upload_with_skip(client, fake_claude, admin_headers):
    c = await make_candidate(client, "Hector Vance")
    resume = resume_md("Hector Vance", "Tulsa, OK", "HVAC service")
    sid = await run_interview(
        client, fake_claude, c, level="experienced", name="Hector Vance",
        contact={"location": "Tulsa, OK"}, answers=answers_for(EXPERIENCED_QUESTION_IDS, "hvac"),
        resume=resume, skip={"employment_gaps"}, model_profile=False)
    s = await load(sid)
    answered, skipped, nxt, total = progress(s)
    assert skipped == ["employment_gaps"] and "employment_gaps" not in answered
    assert (nxt, total, len(answered)) == (None, 12, 11)
    snap = build_fact_snapshot(s)
    assert "## Skipped questions" in snap and "Employment gaps" in snap
    assert "hvac: answer for target_role" in snap
    await generate(client, admin_headers, fake_claude, sid)
    assert len(await rows(sid)) == 5


# -------------------------------------------------------------- scenario 3


async def test_s3_new_graduate_early_career(client, fake_claude):
    c = await make_candidate(client, "Mia Tran")
    resume = resume_md("Mia Tran", "Austin, TX", "Marketing")
    sid = await run_interview(
        client, fake_claude, c, level="early_career", name="Mia Tran", contact={"location": "Austin, TX"},
        answers=answers_for(EARLY_CAREER_QUESTION_IDS, "grad"), resume=resume, skip={"internships"})
    s = await load(sid)
    assert progress(s)[3] == 9 and progress(s)[1] == ["internships"]
    # an experienced-only id is not valid for this track
    fake_claude.script("ok" + meta(discovery_update={"skipped_questions": ["employment_gaps"]}))
    # (still allowed to chat in phase 3; the bad skip is just rejected)
    r = await client.post(SEND, json={"content": "x", "session_id": sid, "client_message_id": str(uuid.uuid4())},
                          headers=c["headers"])
    assert r.status_code == 200
    assert "employment_gaps" not in (await load(sid)).discovery_data.get("skipped_questions", [])


# -------------------------------------------------------------- scenario 4


async def test_s4_career_changer_detail_never_counts(client, fake_claude):
    c = await make_candidate(client, "Dana Whitfield")
    sid = await current_sid(client, c)
    await turn(client, fake_claude, c, sid, "ok" + meta(profile_slug=get_available_profiles()[0], phase=1))
    await turn(client, fake_claude, c, sid, "saved" + meta(
        experience_level="experienced", phase=2,
        discovery_update={"candidate_name": "Dana Whitfield", "contact": {"omitted": ["phone"]}}))
    await turn(client, fake_claude, c, sid, "q1" + meta(discovery_update={
        "target_role": "Instructional designer", "transferable": "lesson design, assessment, coaching"}))
    s = await load(sid)
    answered, _, nxt, _ = progress(s)
    assert answered == ["target_role"] and nxt == "career_narrative"  # detail did not advance
    assert "question 2 of 12 (id `career_narrative`)" in await prompt_for(sid)
    # transferable detail under `context` once that question comes up
    for qid in EXPERIENCED_QUESTION_IDS[1:10]:
        await turn(client, fake_claude, c, sid, "next" + meta(discovery_update={qid: "x"}))
    await turn(client, fake_claude, c, sid, "next" + meta(discovery_update={
        "context": {"background": "high-school teacher", "transferable": "curriculum design"}}))
    s = await load(sid)
    assert progress(s)[2] == "skills_matrix"
    snap = build_fact_snapshot(s)
    assert "curriculum design" in snap and "lesson design, assessment, coaching" in snap


# -------------------------------------------------------------- scenario 5


async def test_s5_industry_without_profile(client, fake_claude, admin_headers, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "PROFILES_DIR", str(tmp_path))
    reload_system_files()
    try:
        c = await make_candidate(client, "Priya Nair")
        sid = await current_sid(client, c)
        system = await prompt_for(sid)
        assert "need to generate one" in system
        # the model cannot select a profile that doesn't exist
        await turn(client, fake_claude, c, sid, "x" + meta(profile_slug="grant_program_manager", phase=1))
        assert (await load(sid)).phase == 0
        # admin generates it (fake provider); nothing real is overwritten (tmp dir)
        fake_claude.script("# Profile: Grant Program Manager\n\n**Industry:** Nonprofit\n\nbody")
        r = await client.post("/api/admin/profiles/generate", headers=admin_headers,
                              json={"role_name": "Grant Program Manager", "industry": "Nonprofit"})
        assert r.status_code == 200, r.text
        assert os.listdir(tmp_path) == ["grant_program_manager.md"]
        assert "grant_program_manager" in await prompt_for(sid)
        await turn(client, fake_claude, c, sid, "x" + meta(profile_slug="grant_program_manager", phase=1))
        s = await load(sid)
        assert (s.phase, s.profile_slug) == (1, "grant_program_manager")
        assert "Grant Program Manager" in await prompt_for(sid)  # the profile text is in the prompt
        # real profiles were untouched
        assert not os.path.exists(os.path.join(os.environ.get("PROFILES_DIR", "/nonexistent"), "grant_program_manager.md"))
    finally:
        monkeypatch.undo()
        reload_system_files()


# -------------------------------------------------------------- scenario 6


async def test_s6_omitted_contact_never_returns(client, fake_claude, admin_headers):
    c = await make_candidate(client, "Luis Okafor")
    upload = ("Luis Okafor\nLogistics coordinator ZZUP6\nlogistics.luis@example.test 214-555-0177\n"
              "https://www.linkedin.com/in/luis-okafor-zz\n")
    resume = resume_md("Luis Okafor", "Dallas, TX", "Logistics")
    sid = await run_interview(
        client, fake_claude, c, level="experienced", name="Luis Okafor",
        contact={"location": "Dallas, TX", "omitted": ["phone", "email", "linkedin"]},
        answers=answers_for(EXPERIENCED_QUESTION_IDS, "logi"), resume=resume, upload=upload)
    # later turns never carry a contact instruction
    s = await load(sid)
    for phase in (2, 3):
        s.phase = phase
        assert CONTACT_MARK not in build_system_prompt(s)
    assert s.discovery_data["contact"] == {"location": "Dallas, TX", "omitted": ["phone", "email", "linkedin"]}
    # snapshot (approved): no upload, no omitted details
    snap = build_fact_snapshot(await load(sid))
    for leak in ("logistics.luis", "214-555", "linkedin.com", "ZZUP6"):
        assert leak not in snap
    assert "phone, email, linkedin" in snap
    # legacy snapshot (no approved resume): the upload comes redacted, chat answers included
    legacy = await load(sid)
    legacy.approved_resume = None
    lsnap = build_fact_snapshot(legacy, ["Please leave my phone and email off."])
    for leak in ("logistics.luis", "214-555", "linkedin.com"):
        assert leak not in lsnap
    assert "ZZUP6" in lsnap and "Candidate's answers, in order" in lsnap
    calls = await generate(client, admin_headers, fake_claude, sid)
    for call in calls:
        blob = call["system"] + json.dumps(call["messages"])
        assert "214-555" not in blob and "logistics.luis" not in blob and "ZZUP6" not in blob
    for r in await rows(sid):
        if r.type != "resume_docx":
            body = open(r.file_path, encoding="utf-8").read()
            assert "214-555" not in body and "@" not in body


# -------------------------------------------------------------- scenario 7


async def test_s7_correction_keeps_only_the_new_value(client, fake_claude):
    c = await make_candidate(client, "Tessa Brandt")
    sid = await current_sid(client, c)
    await turn(client, fake_claude, c, sid, "x" + meta(profile_slug=get_available_profiles()[0], phase=1))
    await turn(client, fake_claude, c, sid, "x" + meta(
        experience_level="experienced", phase=2,
        discovery_update={"candidate_name": "Tessa Brandt", "contact": {"omitted": ["phone"]}}))
    await turn(client, fake_claude, c, sid, "x" + meta(discovery_update={"target_role": "Operations manager"}))
    await turn(client, fake_claude, c, sid, "x" + meta(discovery_update={"career_narrative": "OLDVALUE nine years in retail"}))
    for qid in ("differentiator", "hidden_achievements", "metrics_per_role"):
        await turn(client, fake_claude, c, sid, "x" + meta(discovery_update={qid: "a"}))
    await turn(client, fake_claude, c, sid, "Updated." + meta(
        discovery_update={"career_narrative": "NEWVALUE nine years in retail, six leading stores"}),
        content="Actually, six of those years were leading stores.")
    s = await load(sid)
    assert progress(s)[2] == "leadership_influence"  # a correction doesn't move the question
    snap = build_fact_snapshot(s)
    assert "NEWVALUE" in snap and "OLDVALUE" not in snap
    # with an approved resume the chat history isn't in the snapshot either
    s.approved_resume = "# Tessa\n"
    assert "OLDVALUE" not in build_fact_snapshot(s, ["OLDVALUE nine years in retail"])


# -------------------------------------------------------------- scenario 8


async def test_s8_refresh_mid_interview(client, fake_claude):
    c = await make_candidate(client, "Omar Haddad")
    sid = await current_sid(client, c)
    await turn(client, fake_claude, c, sid, "x" + meta(profile_slug=get_available_profiles()[0], phase=1))
    await turn(client, fake_claude, c, sid, "x" + meta(
        experience_level="experienced", phase=2,
        discovery_update={"candidate_name": "Omar Haddad", "contact": {"omitted": ["phone"]}}))
    for qid in EXPERIENCED_QUESTION_IDS[:4]:
        await turn(client, fake_claude, c, sid, "q" + meta(discovery_update={qid: "a"}))
    # "refresh": everything is reloaded from the server
    msgs = (await client.get("/api/chat/messages", headers=c["headers"])).json()
    sess = (await client.get("/api/chat/session", headers=c["headers"])).json()
    assert sess["id"] == sid and sess["phase"] == 2
    assert len(msgs) == 12 and all(m["status"] == "ok" for m in msgs)
    _, system = await turn(client, fake_claude, c, sid, "next")
    assert "question 5 of 12 (id `metrics_per_role`)" in system
    assert "RESUMING SESSION" in system and "already answered or skipped 4" in system


# -------------------------------------------------------------- scenario 9


async def test_s9_temporary_503_then_retry(client, fake_sdk):
    c = await make_candidate(client, "Greta Lindqvist")
    sid = await current_sid(client, c)
    cmid = str(uuid.uuid4())
    body = {"content": "Nursing", "session_id": sid, "client_message_id": cmid}
    fake_sdk.script(sdk_timeout(), "Got it." + meta(profile_slug=get_available_profiles()[0], phase=1))
    r = await client.post(SEND, json=body, headers=c["headers"])
    assert r.status_code == 503 and r.json()["code"] == "model_unavailable"
    s = await load(sid)
    assert s.phase == 0 and s.profile_slug is None
    r = await client.post(SEND, json=body, headers=c["headers"])
    assert r.status_code == 200
    s = await load(sid)
    assert s.phase == 1 and s.profile_slug
    msgs = (await client.get("/api/chat/messages", headers=c["headers"])).json()
    assert [(m["role"], m["status"]) for m in msgs] == [("user", "ok"), ("assistant", "ok")]


# ------------------------------------------------------------- scenario 10


async def test_s10_new_interview_after_completion(client, fake_claude, admin_headers):
    c = await make_candidate(client, "Nell Ashworth")
    resume = resume_md("Nell Ashworth", "Reno, NV", "Nonprofit program management")
    sid = await run_interview(
        client, fake_claude, c, level="experienced", name="Nell Ashworth", contact={"location": "Reno, NV"},
        answers=answers_for(EXPERIENCED_QUESTION_IDS, "np"), resume=resume)
    await generate(client, admin_headers, fake_claude, sid)
    old_rows = {r.id for r in await rows(sid)}
    assert len(old_rows) == 5
    r = await client.post("/api/chat/new-session", json={"replaces_session_id": sid}, headers=c["headers"])
    new = r.json()
    assert r.status_code == 200 and new["id"] != sid and new["phase"] == 0
    old = await load(sid)
    assert old.status == "deliverables_generated" and old.approved_resume == resume.strip()
    assert {r.id for r in await rows(sid)} == old_rows
    assert (await load(new["id"])).discovery_data in (None, {})
    assert "Phase 0" in await prompt_for(new["id"])


# ---------------------------------------------------------------- extras


async def test_premature_completion_and_phase_rejected(client, fake_claude):
    c = await make_candidate(client, "Wes Calder")
    sid = await current_sid(client, c)
    await turn(client, fake_claude, c, sid, "x" + meta(profile_slug=get_available_profiles()[0], phase=1))
    await turn(client, fake_claude, c, sid, "x" + meta(
        experience_level="experienced", phase=2,
        discovery_update={"candidate_name": "Wes Calder", "contact": {"omitted": ["phone"]}}))
    for qid in EXPERIENCED_QUESTION_IDS[:8]:  # 4 short of 12
        await turn(client, fake_claude, c, sid, "q" + meta(discovery_update={qid: "a"}))
    await turn(client, fake_claude, c, sid, "done?" + meta(phase=3, status="interview_complete"))
    s = await load(sid)
    assert s.phase == 2 and s.status == "active" and s.approved_resume is None
    # phase 3 without any RESUME draft cannot complete either
    s2 = await make_candidate(client, "Xena Pruitt")
    sid2 = await current_sid(client, s2)
    async with async_session() as db:
        row = await db.get(Session, uuid.UUID(sid2))
        row.phase, row.experience_level = 3, "experienced"
        row.discovery_data = {**{q: "a" for q in EXPERIENCED_QUESTION_IDS}, "contact": {"omitted": ["phone"]}}
        await db.commit()
    await turn(client, fake_claude, s2, sid2, "no resume shown" + meta(status="interview_complete"))
    row = await load(sid2)
    assert row.status == "active" and row.approved_resume is None


async def test_resume_markers_stripped_and_unterminated(client, fake_claude):
    clean, draft = extract_resume("Intro\n<!--RESUME-->\n# Name\n- a\n<!--/RESUME-->\nOutro")
    assert draft == "# Name\n- a" and "RESUME" not in clean and "# Name" in clean
    clean, draft = extract_resume("a<!--RESUME-->first<!--/RESUME-->b<!--RESUME-->second<!--/RESUME-->")
    assert draft == "second" and clean == "afirstbsecond"
    clean, draft = extract_resume("Here<!--RESUME-->\n# Name\ncut off")
    assert draft is None and "RESUME" not in clean and "cut off" in clean
    # through the router: stored message keeps the text, the draft isn't saved
    c = await make_candidate(client, "Yuri Ostrov")
    sid = await current_sid(client, c)
    async with async_session() as db:
        row = await db.get(Session, uuid.UUID(sid))
        row.phase = 3
        await db.commit()
    shown, _ = await turn(client, fake_claude, c, sid, "Here: <!--RESUME-->\n# Yuri\n- led teams")
    assert "RESUME" not in shown["content"] and "led teams" in shown["content"]
    assert (await load(sid)).resume_draft is None
    # a RESUME in phase < 3 is ignored too
    c2 = await make_candidate(client, "Zed Park")
    sid2 = await current_sid(client, c2)
    shown, _ = await turn(client, fake_claude, c2, sid2, "<!--RESUME-->\n# Zed\n<!--/RESUME-->")
    assert (await load(sid2)).resume_draft is None


def test_progress_rules():
    class S:
        experience_level = "experienced"
        discovery_data = {"target_role": "x", "career_narrative": "", "metrics_per_role_detail": "d",
                          "skipped_questions": ["differentiator", "bogus"], "contact": {"omitted": ["phone"]}}

    answered, skipped, nxt, total = progress(S)
    assert answered == ["target_role"] and skipped == ["differentiator"]
    assert nxt == "career_narrative" and total == 12  # empty answer and extra keys never count
    assert not discovery_complete(S)
    S.experience_level = "early_career"
    assert progress(S)[3] == 9


# ------------------------------------------------- post-generation checks


async def _legacy_session(client, name, contact, upload=None):
    c = await make_candidate(client, name)
    async with async_session() as db:
        s = Session(user_id=c["id"], phase=3, status="interview_complete", experience_level="experienced",
                    resume_text=upload,
                    discovery_data={"candidate_name": name, "contact": contact, "target_role": "Tech"})
        db.add(s)
        await db.commit()
        return s.id


async def test_check_regenerates_once_then_passes(client, fake_claude, admin_headers):
    sid = await _legacy_session(client, "Ivan Petrov", {"email": "ivan.p@example.test", "omitted": ["phone"]},
                                upload="Ivan 555-123-4567")
    good = "# Ivan Petrov\n\nivan.p@example.test\n\n- Fixed HVAC units"
    calls = await generate(client, admin_headers, fake_claude, sid, replies=(
        "# Ivan\n\nCall [Phone] now", good, PREP, MATRIX, SCORE))
    assert len(calls) == 5  # one automatic regeneration of the resume
    assert "[Phone]" not in open(next(r.file_path for r in await rows(sid) if r.type == "resume_md")).read()
    s = await load(sid)
    assert s.generation_status == "done"
    # legacy prompt: redacted upload, chat answers section absent only because there were no messages
    first = calls[0]["messages"][0]["content"]
    assert "555-123-4567" not in first


@pytest.mark.parametrize("bad", [
    "Reach me at other.person@example.test",
    "Phone 214-555-0199",
    "Lorem ipsum",
    "Growth of XX% last year",
    "Contact email@example.com",
    "see candidates/foo/discovery.md",
    "<!--META:{}--> text",
])
async def test_check_fails_after_second_bad_output_and_is_not_cached(client, fake_claude, admin_headers, bad):
    sid = await _legacy_session(client, "Ada Reyes", {"omitted": ["phone", "email"]})
    await generate(client, admin_headers, fake_claude, sid, replies=(bad, bad))
    s = await load(sid)
    assert s.generation_status == "failed"
    assert s.generation_error == "The resume included contact details or placeholders that weren't confirmed."
    assert await rows(sid) == []
    # the bad document was not cached as a good staged file: a retry generates again
    calls = await generate(client, admin_headers, fake_claude, sid, replies=(
        "# Ada Reyes\n\n- Ran dispatch", PREP, MATRIX, SCORE))
    assert len(calls) == 4
    assert (await load(sid)).generation_status == "done"


async def test_chat_answers_in_legacy_prompt_and_gaps_comments(client, fake_claude, admin_headers):
    sid = await _legacy_session(client, "Bea Lund", {"omitted": ["phone", "email"]})
    async with async_session() as db:
        db.add(Message(session_id=sid, role="user", content="I led a team of nine.", phase=2, status="ok"))
        db.add(Message(session_id=sid, role="user", content="LOST turn", phase=2, status="failed"))
        await db.commit()
    calls = await generate(client, admin_headers, fake_claude, sid, replies=(
        "# Bea Lund\n\n- Led a team", PREP, MATRIX, SCORE))
    first = calls[0]["messages"][0]["content"]
    assert "later answers correct earlier ones" in first and "I led a team of nine." in first
    assert "LOST turn" not in first
    # targeted: GAP comments leave the resume and appear in the cover letter preview only
    fake_claude.script(
        "# Bea Lund\n\n## Summary\nPlanner. <!-- GAP: Kubernetes -->\n",
        "Dear Acme,\n\nI plan well.\n")
    r = await client.post("/api/deliverables/target", headers=admin_headers, json={
        "session_id": str(sid), "company": "Acme", "role": "Planner",
        "posting_text": "Needs Kubernetes", "include_cover_letter": True})
    assert r.status_code == 202, r.text
    await wait_for_generation_tasks()
    targeted = {r.type: r for r in await rows(sid) if r.kind == "targeted"}
    assert set(targeted) == {"resume_targeted_md", "resume_targeted_docx", "cover_letter_md", "cover_letter_docx"}
    assert "GAP" not in open(targeted["resume_targeted_md"].file_path).read()
    assert "GAP" not in "\n".join(docx_lines(targeted["resume_targeted_docx"].file_path))
    cover = open(targeted["cover_letter_md"].file_path).read()
    assert "Gaps to address" in cover and "Kubernetes" in cover
    assert "Kubernetes" not in "\n".join(docx_lines(targeted["cover_letter_docx"].file_path))
