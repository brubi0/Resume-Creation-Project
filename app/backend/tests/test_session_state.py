"""Stage 3: META extraction and validation (pure unit tests, no DB)."""

import logging
import types
import uuid

import pytest

from app.interview import EXPERIENCED_QUESTION_IDS, required_question_ids
from app.session_state import discovery_complete, extract_meta, validate_updates

PROFILES = ["financial_controller", "icu_nurse"]


def sess(**kw):
    base = dict(id=uuid.uuid4(), phase=0, experience_level=None, profile_slug=None,
                status="active", discovery_data={})
    base.update(kw)
    return types.SimpleNamespace(**base)


def val(session, *metas):
    return validate_updates(session, list(metas), available_profiles=PROFILES)


def full_discovery(level="experienced"):
    d = {q: "answer" for q in required_question_ids(level)}
    d["contact"] = {"omitted": ["phone"]}
    return d


# ------------------------------------------------------------ extraction


def test_extract_removes_every_block_and_collects_each():
    text = 'Hi<!--META:{"phase":1}--> there <!--META:{"profile_slug":"x"}-->'
    clean, metas = extract_meta(text)
    assert clean == "Hi there" and "META" not in clean
    assert metas == [{"phase": 1}, {"profile_slug": "x"}]


def test_extract_non_object_and_malformed_become_none():
    clean, metas = extract_meta('A<!--META:[1,2]-->B<!--META:{bad json-->C<!--META:"s"-->')
    assert clean == "ABC" and metas == [None, None, None]


def test_extract_truncated_tail_is_stripped():
    clean, metas = extract_meta('Answer here.<!--META:{"phase": 2, "disc')
    assert clean == "Answer here." and "META" not in clean
    assert metas == [None]


def test_extract_nothing_left_is_empty():
    clean, _ = extract_meta('<!--META:{"phase":1}-->')
    assert clean == ""


# ------------------------------------------------------------ phase


@pytest.mark.parametrize("bad", [99, -1, "2", True, 1.0, None, [1]])
def test_phase_bad_values_rejected(bad):
    acc, rej = val(sess(phase=1, experience_level="experienced"), {"phase": bad})
    assert "phase" not in acc and rej


def test_phase_jump_rejected_and_single_step_allowed():
    s = sess(phase=1, experience_level="experienced")
    assert val(s, {"phase": 3})[0] == {}
    assert val(s, {"phase": 2})[0] == {"phase": 2}
    assert val(s, {"phase": 1})[0] == {}  # staying is a no-op


def test_phase_prerequisites():
    assert val(sess(phase=0), {"phase": 1})[0] == {}
    assert val(sess(phase=0), {"profile_slug": "icu_nurse", "phase": 1})[0] == {
        "profile_slug": "icu_nurse", "phase": 1}
    assert val(sess(phase=1), {"phase": 2})[0] == {}
    assert val(sess(phase=1), {"experience_level": "early_career", "phase": 2})[0] == {
        "experience_level": "early_career", "phase": 2}
    s = sess(phase=2, experience_level="experienced", discovery_data={"contact": {}})
    assert val(s, {"phase": 3})[0] == {}
    s = sess(phase=2, experience_level="experienced", discovery_data=full_discovery())
    assert val(s, {"phase": 3})[0] == {"phase": 3}


def test_phase_moves_with_discovery_in_same_update():
    s = sess(phase=2, experience_level="experienced",
             discovery_data={q: "a" for q in EXPERIENCED_QUESTION_IDS[:-1]})
    meta = {"discovery_update": {"skills_matrix": "done", "contact": {"email": "a@b.co"}},
            "phase": 3}
    assert val(s, meta)[0]["phase"] == 3


def test_discovery_complete_counts_skipped():
    d = {q: "a" for q in EXPERIENCED_QUESTION_IDS[:-1]}
    d["skipped_questions"] = ["skills_matrix"]
    assert not discovery_complete("experienced", d)  # no contact
    d["contact"] = {"omitted": ["phone", "email"]}
    assert discovery_complete("experienced", d)


# ------------------------------------------------------------ other keys


def test_status_rules():
    s3 = sess(phase=3, experience_level="experienced")
    assert val(s3, {"status": "interview_complete"})[0] == {"status": "interview_complete"}
    assert val(sess(phase=2), {"status": "interview_complete"})[0] == {}  # premature
    for bad in ("deliverables_generated", "abandoned", "active", None, "x", 5):
        acc, rej = val(s3, {"status": bad})
        assert "status" not in acc and rej


def test_unknown_fields_and_non_object_and_malformed_meta():
    acc, rej = val(sess(), {"role": "admin", "user_id": "x"}, None, None)
    assert acc == {} and set(rej) == {"unknown_key", "meta_malformed"}


def test_two_blocks_merge_later_wins():
    s = sess(phase=0)
    acc, _ = val(s, {"profile_slug": "icu_nurse", "phase": 1},
                 {"profile_slug": "financial_controller"})
    assert acc == {"profile_slug": "financial_controller", "phase": 1}
    acc, _ = val(s, {"discovery_update": {"a": 1}}, {"discovery_update": {"b": 2}})
    assert acc["discovery_data"] == {"a": 1, "b": 2}


def test_profile_and_level_validation():
    assert val(sess(), {"profile_slug": "nope"})[1]
    assert val(sess(), {"experience_level": "senior"})[1]
    locked = sess(phase=2, experience_level="experienced")
    acc, rej = val(locked, {"experience_level": "early_career"})
    assert acc == {} and rej
    assert val(sess(phase=1), {"experience_level": "early_career"})[0] == {
        "experience_level": "early_career"}


# ------------------------------------------------------------ discovery


def test_discovery_value_limits():
    s = sess()
    assert val(s, {"discovery_update": {"big": "x" * 9000}})[1]
    assert val(s, {"discovery_update": {"Bad Key": "v"}})[1]
    assert val(s, {"discovery_update": {"deep": {"a": {"b": {"c": {"d": 1}}}}}})[1]
    assert val(s, {"discovery_update": {"ok": {"a": {"b": [1, 2]}}}})[0]["discovery_data"]
    assert val(s, {"discovery_update": "nope"})[1]
    assert val(s, {"discovery_update": {"x": None}})[0] == {}
    # total size
    big = {f"k{i}": "y" * 7000 for i in range(10)}
    acc, rej = val(sess(), {"discovery_update": big})
    assert "discovery_data" not in acc and "discovery_total_size" in rej


def test_discovery_null_deletes():
    s = sess(discovery_data={"target_role": "Nurse", "context": "x"})
    acc, _ = val(s, {"discovery_update": {"target_role": None}})
    assert acc["discovery_data"] == {"context": "x"}


def test_contact_bad_field_and_merge_semantics():
    s = sess(discovery_data={"contact": {"phone": "555", "email": "a@b.co"}})
    acc, rej = val(s, {"discovery_update": {"contact": {"ssn": "123"}}})
    assert "discovery_data" not in acc and rej
    acc, rej = val(s, {"discovery_update": {"contact": {"location": "x" * 201}}})
    assert rej and "discovery_data" not in acc
    acc, _ = val(s, {"discovery_update": {"contact": {"location": "Austin, TX"}}})
    assert acc["discovery_data"]["contact"] == {"phone": "555", "email": "a@b.co",
                                                 "location": "Austin, TX"}
    acc, _ = val(s, {"discovery_update": {"contact": {"phone": None}}})
    assert acc["discovery_data"]["contact"] == {"email": "a@b.co"}
    acc, _ = val(s, {"discovery_update": {"contact": {"omitted": ["email", "linkedin"]}}})
    assert acc["discovery_data"]["contact"] == {"phone": "555",
                                                 "omitted": ["email", "linkedin"]}
    acc, rej = val(s, {"discovery_update": {"contact": {"omitted": ["ssn"]}}})
    assert rej


def test_candidate_name_and_skipped_questions():
    s = sess()
    assert val(s, {"discovery_update": {"candidate_name": "n" * 121}})[1]
    assert val(s, {"discovery_update": {"candidate_name": 5}})[1]
    assert val(s, {"discovery_update": {"skipped_questions": "a"}})[1]
    assert val(s, {"discovery_update": {"skipped_questions": ["a", 1]}})[1]
    assert val(s, {"discovery_update": {"skipped_questions": ["context"]}})[0]


def test_rejection_log_has_no_values(caplog):
    secret = "SECRET-VALUE-123"
    with caplog.at_level(logging.WARNING, logger="app.session_state"):
        val(sess(), {"status": secret, "phase": secret, secret: 1})
    assert "rejected=" in caplog.text and "session=" in caplog.text
    assert secret not in caplog.text
