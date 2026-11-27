"""Test harness. Runs inside the `resumetest` compose project (see run-tests.sh).

Settings are read at import time (app/config.py), so every env var comes from
docker-compose.test.yml. Do not set them here.

Claude seam (Stage 1): other modules do `from app.claude_client import
create_message / stream_message`, so the `fake_claude` fixture patches those
names where they are looked up (claude_service, deliverables, admin_router) and
also on app.claude_client itself. The real Anthropic client is never called;
the env also points ANTHROPIC_BASE_URL at a dead port as a belt-and-braces guard.
Stage 4 makes the seam async; update FakeClaude then.
"""

import asyncio
import os
import time
import types
import uuid

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
    """Scripted stand-in for create_message/stream_message.

    script(*items): each item is consumed per call and may be
      - str: returned as the model's text
      - Exception instance: raised
      - callable(kwargs) -> str | Exception: evaluated per call
      - ("sleep", seconds, item): blocks (sync seam at Stage 1) then behaves as item
    Any call with an empty queue fails the test.
    """

    def __init__(self):
        self.queue: list = []
        self.calls: list[dict] = []
        self.unscripted = 0

    def script(self, *items):
        self.queue.extend(items)
        return self

    def _next(self, kwargs):
        self.calls.append(kwargs)
        if not self.queue:
            self.unscripted += 1
            raise AssertionError("unscripted Claude call in test")
        item = self.queue.pop(0)
        if isinstance(item, tuple) and item and item[0] == "sleep":
            time.sleep(item[1])
            item = item[2]
        if callable(item) and not isinstance(item, Exception):
            item = item(kwargs)
        if isinstance(item, Exception):
            raise item
        return make_response(item)

    # Same signatures as app.claude_client (sync at Stage 1)
    def create_message(self, client, *, effort="medium", **kwargs):
        return self._next({"effort": effort, **kwargs})

    def stream_message(self, client, *, effort="medium", **kwargs):
        return self._next({"effort": effort, **kwargs})


@pytest.fixture
def fake_claude(monkeypatch):
    import app.claude_client as cc

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
