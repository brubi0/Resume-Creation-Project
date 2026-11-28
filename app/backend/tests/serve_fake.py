"""E2E-only API server with a scripted fake provider (never the real Anthropic API).

    python -m tests.serve_fake        (compose profile `e2e`, see app/e2e/run-journey.sh)

Imports the real app, replaces the provider seam (create_message / stream_message, where
every module looks them up) with a scripted interviewer, and runs uvicorn. The interviewer
is stateless: it decides its reply from the system prompt the app built (phase, question
id) and the stored conversation, so a browser run exercises the real prompts, META
validation, progress tracking, approval and document generation.

Scenario: experienced HVAC manager, no upload -> contact -> 12 questions -> phase 3 resume
-> approval -> interview_complete. Document generation (3 model calls; the resume is the
approved text) returns small synthetic documents.
"""

import json
import os
import re
import types
from pathlib import Path

import uvicorn

# Same guard as the test suite: a dead address, so a leak fails fast instead of billing.
os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:9"
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import app.claude_client as cc  # noqa: E402
import app.claude_service  # noqa: E402,F401
import app.deliverables  # noqa: E402,F401
import app.routers.admin_router  # noqa: E402,F401
from app.interview import EXPERIENCED_QUESTION_IDS  # noqa: E402
from app.main import app  # noqa: E402

FIX = Path(__file__).parent / "fixtures" / "documents" / "experienced"
NAME = os.environ.get("E2E_CANDIDATE_NAME", "Maximiliano Alejandro Fernández-Oyelaran")
CONTACT = {
    "location": "Austin, TX",
    "email": "max.fernandez@example.test",
    "phone": "(512) 555-0147",
    "linkedin": "linkedin.com/in/example-maximiliano",
}
RESUME = (FIX / "resume.md").read_text(encoding="utf-8")
PREP = (FIX / "interview_prep.md").read_text(encoding="utf-8")
MATRIX = (FIX / "skills_matrix.html").read_text(encoding="utf-8")
SCORE = (FIX / "score_card.md").read_text(encoding="utf-8")

_Q_RE = re.compile(r"question (\d+) of (\d+) \(id `([a-z_]+)`\)")
_PHASE_RE = re.compile(r"\(Phase (\d)\)")


def meta(**kw) -> str:
    return f"<!--META:{json.dumps(kw)}-->"


def _response(text: str):
    return types.SimpleNamespace(
        stop_reason="end_turn",
        content=[
            types.SimpleNamespace(type="thinking", thinking="...", text=None),
            types.SimpleNamespace(type="text", text=text),
        ],
    )


def _text_of(msg) -> str:
    c = msg.get("content")
    return c if isinstance(c, str) else json.dumps(c)


def interviewer(system: str, messages: list[dict]) -> str:
    m = _PHASE_RE.search(system)
    phase = int(m.group(1)) if m else 0
    assistant_said = " ".join(_text_of(x) for x in messages if x.get("role") == "assistant")

    if phase == 0:
        slug = sorted(p.stem for p in Path(os.environ["PROFILES_DIR"]).glob("*.md") if p.stem != "README")[0]
        return "Which field are you in?" + meta(profile_slug=slug, phase=1)
    if phase == 1:
        if "Is this contact info current?" not in assistant_said:
            return "Welcome. Is this contact info current?"
        return ("Thanks, saved. Question 1 of 12 is next: what role are you targeting?" + meta(
            experience_level="experienced", phase=2,
            discovery_update={"candidate_name": NAME, "contact": CONTACT}))
    if phase == 2:
        q = _Q_RE.search(system)
        if not q:  # all answered; move on
            return "That is everything I need." + meta(phase=3)
        n, total, qid = int(q.group(1)), int(q.group(2)), q.group(3)
        update = {"discovery_update": {qid: f"E2E answer for {qid}: about 30 percent better results."}}
        if n == total:
            return "That is all twelve questions. Shall I draft your resume?" + meta(phase=3, **update)
        return f"Got it. Question {n + 1} of {total} is next." + meta(**update)
    if phase == 3:
        if "Here is your resume." in assistant_said:
            return "Wonderful, your interview is complete." + meta(status="interview_complete")
        return ("Here is your resume.\n<!--RESUME-->\n" + RESUME.strip() + "\n<!--/RESUME-->\n"
                "Any changes before I finalize?")
    return "Done."


def doc_writer(system: str) -> str:
    low = system.lower()
    if "interview coach" in low:
        return PREP
    if "skills matrix" in low:
        return MATRIX
    if "resume evaluator" in low:
        return SCORE
    raise AssertionError("unscripted document call")


async def fake_create_message(*, effort="medium", **kw):
    return _response(interviewer(kw["system"], kw["messages"]))


async def fake_stream_message(*, effort="medium", **kw):
    return _response(doc_writer(kw["system"]))


def install() -> None:
    assert EXPERIENCED_QUESTION_IDS  # sanity: ids come from the app, not from here
    for mod in ("app.claude_client", "app.claude_service", "app.deliverables", "app.routers.admin_router"):
        module = __import__(mod, fromlist=["x"])
        if hasattr(module, "create_message"):
            module.create_message = fake_create_message
        if hasattr(module, "stream_message"):
            module.stream_message = fake_stream_message
    cc.get_client = lambda: (_ for _ in ()).throw(AssertionError("real provider client requested"))


install()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), log_level="warning")
