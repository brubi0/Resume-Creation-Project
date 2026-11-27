"""Treat the model's META block as untrusted *proposed* updates.

extract_meta strips every META block from the reply; validate_updates checks the
merged proposal against the freshly locked session and returns only what is
allowed. Rejections are logged as reason keys only, never values or text.
"""

import json
import logging
import math
import re

from app.interview import discovery_complete_for, known_question_ids

logger = logging.getLogger(__name__)

_META_RE = re.compile(r"<!--META:(.*?)-->", re.DOTALL)
_META_OPEN = "<!--META:"

ALLOWED_KEYS = {"phase", "experience_level", "profile_slug", "status", "discovery_update"}
EXPERIENCE_LEVELS = {"experienced", "early_career"}
DISCOVERY_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
CONTACT_FIELDS = ("location", "phone", "email", "linkedin", "other")
CONTACT_KEYS = set(CONTACT_FIELDS) | {"omitted"}
MAX_VALUE_BYTES = 8 * 1024
MAX_TOTAL_BYTES = 64 * 1024
MAX_DEPTH = 3


def extract_meta(text: str) -> tuple[str, list]:
    """Return (clean_text, metas). Every block (and a truncated trailing one) is removed.

    Each entry of metas is a dict, or None when the block was malformed or not an object.
    """
    metas: list = []
    for m in _META_RE.finditer(text):
        try:
            obj = json.loads(m.group(1))
        except (json.JSONDecodeError, RecursionError):
            obj = None
        metas.append(obj if isinstance(obj, dict) else None)
    clean = _META_RE.sub("", text)
    idx = clean.find(_META_OPEN)
    if idx != -1:  # unterminated tail (truncated reply)
        clean = clean[:idx]
        metas.append(None)
    return clean.strip(), metas


_RESUME_RE = re.compile(r"<!--RESUME-->(.*?)<!--/RESUME-->", re.DOTALL)
_RESUME_OPEN = "<!--RESUME-->"
_RESUME_CLOSE = "<!--/RESUME-->"
MAX_RESUME_BYTES = 64 * 1024


def extract_resume(text: str) -> tuple[str, str | None]:
    """Return (clean_text, draft). The last complete RESUME block is the draft.

    Every marker is stripped from the stored text but the resume text itself stays
    visible to the candidate. An unterminated <!--RESUME--> keeps its text and
    produces no draft.
    """
    blocks = [m.group(1).strip() for m in _RESUME_RE.finditer(text)]
    clean = _RESUME_RE.sub(lambda m: m.group(1), text)
    clean = clean.replace(_RESUME_OPEN, "").replace(_RESUME_CLOSE, "")
    draft = blocks[-1] if blocks else None
    if draft is not None and (not draft or len(draft.encode("utf-8")) > MAX_RESUME_BYTES):
        draft = None
    return clean.strip(), draft


def _depth(v) -> int | None:
    """Nesting depth of a JSON-ish value; None if it holds a disallowed type."""
    if isinstance(v, bool) or isinstance(v, (str, int)):
        return 0
    if isinstance(v, float):
        return 0 if math.isfinite(v) else None
    if isinstance(v, list):
        ds = [_depth(x) for x in v]
    elif isinstance(v, dict):
        if not all(isinstance(k, str) for k in v):
            return None
        ds = [_depth(x) for x in v.values()]
    else:
        return None
    if any(d is None for d in ds):
        return None
    return 1 + max(ds, default=0)


def _json_size(v) -> int:
    return len(json.dumps(v, ensure_ascii=False).encode("utf-8"))


def discovery_complete(experience_level: str | None, discovery_data: dict | None) -> bool:
    return discovery_complete_for(experience_level, discovery_data)


def _merge_contact(existing, update, rejected: list[str]):
    """Field-by-field contact merge. Returns the new contact dict, or None to reject."""
    if not isinstance(update, dict) or not set(update) <= CONTACT_KEYS:
        rejected.append("contact_shape")
        return None
    new = dict(existing) if isinstance(existing, dict) else {}
    omitted_old = new.get("omitted")
    omitted = [o for o in omitted_old if o in CONTACT_FIELDS] if isinstance(omitted_old, list) else []
    for field in CONTACT_FIELDS:
        if field not in update:
            continue
        v = update[field]
        if v is None:
            new.pop(field, None)
        elif isinstance(v, str) and len(v) <= 200:
            if v.strip():
                new[field] = v
                if field in omitted:  # given again, so it is no longer omitted
                    omitted.remove(field)
            else:
                new.pop(field, None)
        else:
            rejected.append("contact_field")
            return None
    if "omitted" in update:
        o = update["omitted"]
        if o is None:
            omitted = []
        elif isinstance(o, list) and all(isinstance(x, str) and x in CONTACT_FIELDS for x in o):
            omitted = list(dict.fromkeys(o))
        else:
            rejected.append("contact_omitted")
            return None
    for f in omitted:
        new.pop(f, None)
    if omitted:
        new["omitted"] = omitted
    else:
        new.pop("omitted", None)
    return new


def _apply_discovery(existing: dict, update, rejected: list[str], level=None) -> dict | None:
    if not isinstance(update, dict):
        rejected.append("discovery_update_type")
        return None
    data = dict(existing or {})
    for key, value in update.items():
        if not isinstance(key, str) or not DISCOVERY_KEY_RE.match(key):
            rejected.append("discovery_key")
            continue
        if value is None:
            data.pop(key, None)
            continue
        if key == "contact":
            # Contact fields may be null (= remove), so it is shape-checked separately.
            if _json_size(value) > MAX_VALUE_BYTES:
                rejected.append("discovery_value_size")
                continue
            merged = _merge_contact(data.get("contact"), value, rejected)
            if merged is None:
                continue
            data["contact"] = merged
            continue
        d = _depth(value)
        if d is None or d > MAX_DEPTH:
            rejected.append("discovery_value_type")
            continue
        if _json_size(value) > MAX_VALUE_BYTES:
            rejected.append("discovery_value_size")
            continue
        if key == "candidate_name":
            if not isinstance(value, str) or len(value) > 120:
                rejected.append("candidate_name")
                continue
            data[key] = value
        elif key == "skipped_questions":
            known = known_question_ids(level)
            if not isinstance(value, list) or not all(isinstance(x, str) and x in known for x in value):
                rejected.append("skipped_questions")
                continue
            data[key] = list(dict.fromkeys(value))
        else:
            data[key] = value
    if _json_size(data) > MAX_TOTAL_BYTES:
        rejected.append("discovery_total_size")
        return None
    return data


def validate_updates(
    session, metas: list, *, available_profiles, resume_draft: str | None = None
) -> tuple[dict, list[str]]:
    """Return (accepted session-field updates, rejected reason keys)."""
    rejected: list[str] = []
    merged: dict = {}
    for m in metas:
        if m is None:
            rejected.append("meta_malformed")
            continue
        for k, v in m.items():
            if k == "discovery_update" and isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
    for k in merged:
        if k not in ALLOWED_KEYS:
            rejected.append("unknown_key")

    accepted: dict = {}
    cur_phase = session.phase
    cur_level = session.experience_level
    cur_profile = session.profile_slug

    if "profile_slug" in merged:
        v = merged["profile_slug"]
        if isinstance(v, str) and v in set(available_profiles):
            if v != cur_profile:
                accepted["profile_slug"] = v
        else:
            rejected.append("profile_slug")
    profile = accepted.get("profile_slug", cur_profile)

    if "experience_level" in merged:
        v = merged["experience_level"]
        if not isinstance(v, str) or v not in EXPERIENCE_LEVELS:
            rejected.append("experience_level")
        elif cur_phase >= 2 and cur_level is not None and v != cur_level:
            rejected.append("experience_level_locked")
        elif v != cur_level:
            accepted["experience_level"] = v
    level = accepted.get("experience_level", cur_level)

    data = session.discovery_data or {}
    if "discovery_update" in merged:
        new_data = _apply_discovery(data, merged["discovery_update"], rejected, level)
        if new_data is not None and new_data != data:
            accepted["discovery_data"] = new_data
            data = new_data

    phase = cur_phase
    if "phase" in merged:
        v = merged["phase"]
        if isinstance(v, bool) or not isinstance(v, int):
            rejected.append("phase_type")
        elif v < 0 or v > 3:
            rejected.append("phase_range")
        elif v == cur_phase:
            pass
        elif v != cur_phase + 1:
            rejected.append("phase_jump")
        elif cur_phase == 0 and not profile:
            rejected.append("phase_needs_profile")
        elif cur_phase == 1 and not level:
            rejected.append("phase_needs_level")
        elif cur_phase == 2 and not discovery_complete(level, data):
            rejected.append("phase_needs_discovery")
        else:
            accepted["phase"] = v
            phase = v

    # The draft extracted from this reply counts only while the interview is in phase 3.
    draft = getattr(session, "resume_draft", None)
    if resume_draft and phase == 3 and resume_draft != draft:
        accepted["resume_draft"] = resume_draft
        draft = resume_draft

    if "status" in merged:
        v = merged["status"]
        if v == "interview_complete" and phase == 3 and draft and draft.strip():
            if session.status != "interview_complete":
                accepted["status"] = v
            if draft != getattr(session, "approved_resume", None):
                accepted["approved_resume"] = draft
        else:
            rejected.append("status")

    if rejected:
        logger.warning("session=%s rejected=%s", session.id, ",".join(sorted(set(rejected))))
    return accepted, rejected
