"""Test harness. Runs inside the `resumetest` compose project (see run-tests.sh).

Settings are read at import time (app/config.py), so every env var comes from
docker-compose.test.yml. Do not set them here.

Claude seam (Stage 1): other modules do `from app.claude_client import
create_message / stream_message`, so the `fake_claude` fixture patches those
names where they are looked up (claude_service, deliverables, admin_router) and
also on app.claude_client itself. The real Anthropic client is never called;
the env also points ANTHROPIC_BASE_URL at a dead port as a belt-and-braces guard.

Stage 4: the seam is async (`await create_message(...)`, no client argument), and
there are TWO ways to drive it so both layers get exercised:

* `fake_claude` patches create_message/stream_message by name (journey and
  non-blocking tests). Scripted exceptions are raised as-is from the seam.
* `fake_sdk` leaves create_message/stream_message real and patches
  `app.claude_client.get_client` to return a stand-in for AsyncAnthropic whose
  `messages.create` / `messages.stream` consume the same script. Scripted SDK
  exceptions (APITimeoutError, RateLimitError, ...) therefore travel through the
  real `_call` / `_map_error` code and come out as ClaudeUnavailable etc.
  Use this one for every provider-failure test.
"""

import asyncio
import os
import threading
import types
import uuid

import anthropic
import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

assert os.environ.get("ANTHROPIC_BASE_URL") == "http://127.0.0.1:9", (
    "tests must run via run-tests.sh (compose env)"
)

from app.auth import hash_password  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import async_session, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, User  # noqa: E402

ADMIN_PW = os.environ["ADMIN_PASSWORD"]
CANDIDATE_PW = "candidate-pw-1"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _schema():
    """Fresh schema for the whole test session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture(scope="session")
async def client(_schema):
    """AsyncClient over the ASGI app with the lifespan run once."""
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c


async def login(client: AsyncClient, username: str, pw: str) -> dict:
    r = await client.post("/api/auth/login", json={"username": username, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def make_admin_headers(client: AsyncClient) -> dict:
    return await login(client, "admin", ADMIN_PW)


async def make_candidate(client: AsyncClient, name: str) -> dict:
    """Create a candidate (unique username) directly in the DB; return info + headers."""
    username = f"{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}"
    async with async_session() as db:
        user = User(
            name=name,
            username=username,
            password_hash=hash_password(CANDIDATE_PW),
            role="candidate",
        )
        db.add(user)
        await db.commit()
        user_id = user.id
    headers = await login(client, username, CANDIDATE_PW)
    return {"id": user_id, "name": name, "username": username, "headers": headers}


@pytest_asyncio.fixture
async def admin_headers(client):
    return await make_admin_headers(client)


@pytest.fixture
def deliverables_dir():
    os.makedirs(settings.DELIVERABLES_DIR, exist_ok=True)
    return settings.DELIVERABLES_DIR


# ---------------------------------------------------------------------------
# Fake Claude
# ---------------------------------------------------------------------------


def make_response(text: str, stop_reason: str = "end_turn"):
    """Shaped like an Anthropic Message: a thinking block first, then text."""
    return types.SimpleNamespace(
        stop_reason=stop_reason,
        content=[
            types.SimpleNamespace(type="thinking", thinking="...", text=None),
            types.SimpleNamespace(type="text", text=text),
        ],
    )


class FakeClaude:
    """Scripted stand-in for create_message/stream_message (async seam).

    script(*items): each item is consumed per call and may be
      - str: returned as the model's text
      - a response object from make_response(): returned unchanged
      - Exception instance: raised
      - callable(kwargs) -> str | Exception: evaluated per call
      - ("sleep", seconds, item): `await asyncio.sleep(seconds)`, then behaves as item
      - ("wait", threading.Event, item): awaits the event (in a worker thread, bounded 20 s)
        until it is set, then behaves as item. `started` is set as soon as a call begins, so
        a test can wait for "reply in flight" deterministically (await
        asyncio.to_thread(fake.started.wait, 10)).
    Any call with an empty queue fails the test.
    """

    def __init__(self):
        self.queue: list = []
        self.calls: list[dict] = []
        self.unscripted = 0
        self.started = threading.Event()

    def script(self, *items):
        self.queue.extend(items)
        return self

    async def _next(self, kwargs):
        self.calls.append(kwargs)
        if not self.queue:
            self.unscripted += 1
            raise AssertionError("unscripted Claude call in test")
        item = self.queue.pop(0)
        self.started.set()
        if isinstance(item, tuple) and item and item[0] == "sleep":
            await asyncio.sleep(item[1])
            item = item[2]
        elif isinstance(item, tuple) and item and item[0] == "wait":
            assert await asyncio.to_thread(item[1].wait, 20), (
                "test never released the gated fake reply"
            )
            item = item[2]
        if callable(item) and not isinstance(item, Exception):
            item = item(kwargs)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, str):
            return make_response(item)
        return item

    # Same signatures as app.claude_client (async, no client argument)
    async def create_message(self, *, effort="medium", **kwargs):
        return await self._next({"effort": effort, **kwargs})

    async def stream_message(self, *, effort="medium", **kwargs):
        return await self._next({"effort": effort, **kwargs})


# Real SDK exception instances, constructed the way the SDK itself builds them.
_REQ = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def sdk_timeout() -> anthropic.APITimeoutError:
    return anthropic.APITimeoutError(request=_REQ)


def sdk_connection() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(message="Connection error.", request=_REQ)


def sdk_status(code: int, secret: str = "sk-ant-LEAKED-provider-text"):
    """APIStatusError subclass for an HTTP status; `secret` must never reach a response."""
    resp = httpx.Response(code, request=_REQ, headers={"request-id": "req_test123"})
    cls = {
        400: anthropic.BadRequestError,
        401: anthropic.AuthenticationError,
        403: anthropic.PermissionDeniedError,
        404: anthropic.NotFoundError,
        429: anthropic.RateLimitError,
    }.get(code)
    if cls is None:
        cls = anthropic.InternalServerError if code >= 500 else anthropic.APIStatusError
    return cls(secret, response=resp, body=None)


class _FakeStream:
    def __init__(self, fake, kwargs):
        self._fake, self._kwargs = fake, kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_final_message(self):
        return await self._fake._next(self._kwargs)


class _FakeMessages:
    def __init__(self, fake):
        self._fake = fake

    @staticmethod
    def _clean(kw):
        # what the SDK would receive; drop transport-only args
        return {k: v for k, v in kw.items() if k not in ("timeout",)}

    async def create(self, **kw):
        return await self._fake._next(self._clean(kw))

    def stream(self, **kw):
        return _FakeStream(self._fake, self._clean(kw))


class FakeSDKClient:
    """Stands in for anthropic.AsyncAnthropic underneath the real claude_client."""

    def __init__(self, fake):
        self.messages = _FakeMessages(fake)


@pytest.fixture
def fake_claude(monkeypatch):
    fake = FakeClaude()
    for modname in ("app.claude_client", "app.claude_service", "app.deliverables",
                    "app.routers.admin_router"):
        mod = __import__(modname, fromlist=["x"])
        if hasattr(mod, "create_message"):
            monkeypatch.setattr(mod, "create_message", fake.create_message)
        if hasattr(mod, "stream_message"):
            monkeypatch.setattr(mod, "stream_message", fake.stream_message)
    yield fake
    assert fake.unscripted == 0, "a Claude call was made with no scripted reply"


@pytest.fixture
def fake_sdk(monkeypatch):
    """Scripted AsyncAnthropic underneath the REAL create_message/stream_message."""
    import app.claude_client as cc

    fake = FakeClaude()
    monkeypatch.setattr(cc, "get_client", lambda: FakeSDKClient(fake))
    yield fake
    assert fake.unscripted == 0, "a Claude call was made with no scripted reply"
