"""Stage 4: Claude failure contract, async seam, non-blocking proof.

Provider-failure tests use `fake_sdk` so SDK exceptions go through the real
claude_client mapping (see conftest). The non-blocking proof uses the seam fake.
"""

import asyncio
import time
import uuid

import pytest

import app.claude_client as cc
from app.config import settings

from .conftest import make_candidate, make_response, sdk_connection, sdk_status, sdk_timeout

SEND = "/api/chat/send"
SECRET = "sk-ant-LEAKED-provider-text"


async def _send(client, c, content, sid, cmid):
    return await client.post(
        SEND,
        json={"content": content, "session_id": sid, "client_message_id": cmid},
        headers=c["headers"],
    )


async def _state(client, c):
    msgs = (await client.get("/api/chat/messages", headers=c["headers"])).json()
    sess = (await client.get("/api/chat/session", headers=c["headers"])).json()
    return msgs, sess


FAILURES = [
    ("timeout", sdk_timeout, 503, "model_unavailable"),
    ("connection", sdk_connection, 503, "model_unavailable"),
    ("rate_limit_429", lambda: sdk_status(429), 503, "model_unavailable"),
    ("server_500", lambda: sdk_status(500), 503, "model_unavailable"),
    ("overloaded_529", lambda: sdk_status(529), 503, "model_unavailable"),
    ("auth_401", lambda: sdk_status(401), 503, "model_unavailable"),
    ("forbidden_403", lambda: sdk_status(403), 503, "model_unavailable"),
    ("not_found_404", lambda: sdk_status(404), 503, "model_unavailable"),
    ("refusal", lambda: make_response("", "refusal"), 422, "model_refused"),
    ("max_tokens", lambda: make_response("cut off", "max_tokens"), 503, "model_unavailable"),
    ("empty_text", lambda: make_response("   "), 503, "model_unavailable"),
]


@pytest.mark.parametrize("name,make,status,code", FAILURES, ids=[f[0] for f in FAILURES])
async def test_failure_keeps_answer_then_retry_succeeds(client, fake_sdk, name, make, status, code):
    c = await make_candidate(client, f"Fay {name}")
    sid = (await client.get("/api/chat/session", headers=c["headers"])).json()["id"]
    cmid = str(uuid.uuid4())
    fake_sdk.script(make(), "Welcome back.")
    r = await _send(client, c, "my answer", sid, cmid)
    assert r.status_code == status, r.text
    body = r.json()
    assert body["code"] == code
    assert SECRET not in r.text and "req_test123" not in r.text
    msgs, sess = await _state(client, c)
    assert [(m["role"], m["status"], m["content"]) for m in msgs] == [("user", "failed", "my answer")]
    assert sess["turn_state"] == "idle"
    r = await _send(client, c, "my answer", sid, cmid)
    assert r.status_code == 200, r.text
    msgs, sess = await _state(client, c)
    assert [(m["role"], m["status"]) for m in msgs] == [("user", "ok"), ("assistant", "ok")]
    assert sess["turn_state"] == "idle"


async def test_error_messages_match_contract(client, fake_sdk):
    c = await make_candidate(client, "Msg Check")
    sid = (await client.get("/api/chat/session", headers=c["headers"])).json()["id"]
    fake_sdk.script(sdk_timeout(), sdk_status(401))
    r = await _send(client, c, "a", sid, str(uuid.uuid4()))
    assert r.json()["message"] == "The interviewer didn't respond. Your answer is saved; tap Try again."
    r = await _send(client, c, "b", sid, str(uuid.uuid4()))
    assert r.json()["message"] == "The interviewer is unavailable right now."


async def test_malformed_meta_keeps_text_drops_meta(client, fake_sdk):
    c = await make_candidate(client, "Meta Bad")
    sid = (await client.get("/api/chat/session", headers=c["headers"])).json()["id"]
    fake_sdk.script('Great, tell me more.<!--META:{"phase": 2, broken-->')
    r = await _send(client, c, "hi", sid, str(uuid.uuid4()))
    assert r.status_code == 200
    assert r.json()["content"].startswith("Great, tell me more.")
    assert "META" not in r.json()["content"]
    _, sess = await _state(client, c)
    assert sess["phase"] != 2


async def test_provider_text_never_logged_or_returned(client, fake_sdk, caplog):
    c = await make_candidate(client, "Log Check")
    sid = (await client.get("/api/chat/session", headers=c["headers"])).json()["id"]
    fake_sdk.script(sdk_status(500))
    with caplog.at_level("DEBUG"):
        r = await _send(client, c, "x", sid, str(uuid.uuid4()))
    assert SECRET not in r.text
    assert SECRET not in caplog.text
    assert "req_test123" in caplog.text  # request id is logged


async def test_sdk_mapping_classes():
    from .conftest import FakeClaude, FakeSDKClient

    cases = [
        (sdk_timeout(), cc.ClaudeUnavailable),
        (sdk_connection(), cc.ClaudeUnavailable),
        (sdk_status(429), cc.ClaudeUnavailable),
        (sdk_status(503), cc.ClaudeUnavailable),
        (sdk_status(401), cc.ClaudeConfigError),
        (sdk_status(404), cc.ClaudeConfigError),
        (sdk_status(400), cc.ClaudeConfigError),
    ]
    for exc, expected in cases:
        fake = FakeClaude().script(exc, exc)
        client = FakeSDKClient(fake)
        orig = cc.get_client
        cc.get_client = lambda c=client: c
        try:
            with pytest.raises(expected):
                await cc.create_message(max_tokens=10, messages=[])
            with pytest.raises(expected):  # streaming path maps too
                await cc.stream_message(max_tokens=10, messages=[])
        finally:
            cc.get_client = orig


async def test_beta_header_and_extra_body_preserved(monkeypatch):
    seen = {}

    class M:
        async def create(self, **kw):
            seen.update(kw)
            return make_response("ok")

    class C:
        messages = M()

    monkeypatch.setattr(cc, "get_client", lambda: C())
    await cc.create_message(effort="high", max_tokens=5, messages=[])
    assert seen["model"] == cc.MODEL
    assert seen["extra_headers"] == {"anthropic-beta": "server-side-fallback-2026-07-01"}
    assert seen["extra_body"] == {"fallbacks": "default", "output_config": {"effort": "high"}}
    assert seen["timeout"] == cc.CHAT_TIMEOUT


def test_real_client_is_lazy_async_and_shared(monkeypatch):
    import anthropic

    monkeypatch.setattr(cc, "_client", None)
    a = cc.get_client()
    assert isinstance(a, anthropic.AsyncAnthropic) and a.max_retries == 2
    assert cc.get_client() is a


async def test_slow_provider_does_not_block_event_loop(client, fake_claude):
    a = await make_candidate(client, "Slow Alice")
    b = await make_candidate(client, "Quick Bob")
    sid = (await client.get("/api/chat/session", headers=a["headers"])).json()["id"]
    await client.get("/api/chat/messages", headers=b["headers"])  # warm
    fake_claude.script(("sleep", 3, "Slow reply."))
    task = asyncio.create_task(_send(client, a, "hello", sid, str(uuid.uuid4())))
    assert await asyncio.to_thread(fake_claude.started.wait, 10)
    t0 = time.perf_counter()
    h = await client.get("/api/health")
    t_health = time.perf_counter() - t0
    t0 = time.perf_counter()
    m = await client.get("/api/chat/messages", headers=b["headers"])
    t_msgs = time.perf_counter() - t0
    print(f"NONBLOCKING health={t_health:.3f}s messages={t_msgs:.3f}s")
    assert h.status_code == 200 and m.status_code == 200
    assert t_health < 0.5 and t_msgs < 0.5
    assert not task.done()
    assert (await asyncio.wait_for(task, 15)).status_code == 200


@pytest.mark.parametrize("name,make,status", [
    ("timeout", sdk_timeout, 503),
    ("rate_limit", lambda: sdk_status(429), 503),
    ("auth", lambda: sdk_status(401), 503),
    ("refusal", lambda: make_response("", "refusal"), 422),
    ("max_tokens", lambda: make_response("x", "max_tokens"), 422),
    ("empty", lambda: make_response(""), 422),
])
async def test_profile_generation_maps_errors(client, admin_headers, fake_sdk, monkeypatch, tmp_path, name, make, status):
    monkeypatch.setattr(settings, "PROFILES_DIR", str(tmp_path))
    fake_sdk.script(make())
    r = await client.post("/api/admin/profiles/generate", headers=admin_headers,
                          json={"role_name": f"Role {name}"})
    assert r.status_code == status, r.text
    assert SECRET not in r.text
    assert list(tmp_path.iterdir()) == []


async def test_profile_pause_turn_loop_still_works(client, admin_headers, fake_sdk, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "PROFILES_DIR", str(tmp_path))
    fake_sdk.script(make_response("", "pause_turn"), "# Profile: Welder\n\nbody")
    r = await client.post("/api/admin/profiles/generate", headers=admin_headers,
                          json={"role_name": "Welder"})
    assert r.status_code == 200, r.text
