"""alembic upgrade head on an empty database must match the models."""

import asyncio
import os
import subprocess
import sys

import asyncpg
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.config import settings
from app.models import Base

MIG_DB = "migtest"


async def _recreate_db(url):
    conn = await asyncpg.connect(
        user=url.username, password=url.password, host=url.host,
        port=url.port or 5432, database="postgres",
    )
    try:
        await conn.execute(f"DROP DATABASE IF EXISTS {MIG_DB}")
        await conn.execute(f"CREATE DATABASE {MIG_DB}")
    finally:
        await conn.close()


async def _migrated_diff():
    url = make_url(settings.DATABASE_URL)
    await _recreate_db(url)
    mig_url = url.set(database=MIG_DB)

    env = {**os.environ, "DATABASE_URL": mig_url.render_as_string(hide_password=False)}
    proc = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr

    from sqlalchemy.ext.asyncio import create_async_engine

    eng = create_async_engine(mig_url)
    try:
        async with eng.connect() as conn:
            def _diff(sync_conn):
                ctx = MigrationContext.configure(sync_conn)
                return compare_metadata(ctx, Base.metadata)

            return await conn.run_sync(_diff)
    finally:
        await eng.dispose()


def _flat(diff):
    for d in diff:
        yield from (d if isinstance(d, list) else [d])


async def test_alembic_upgrade_head_has_all_tables_and_columns():
    diff = await _migrated_diff()
    structural = [d for d in _flat(diff)
                  if d[0] in ("add_table", "remove_table", "add_column", "remove_column")]
    assert structural == []


@pytest.mark.xfail(strict=True, reason="known drift: created_at/updated_at are timestamptz in migrations but naive DateTime in models; ix_postings_session_id exists only in the migration")
async def test_alembic_upgrade_head_matches_models_exactly():
    assert await _migrated_diff() == []


async def test_0006_backfills_targeted_kind():
    url = make_url(settings.DATABASE_URL)
    await _recreate_db(url)
    mig_url = url.set(database=MIG_DB)
    env = {**os.environ, "DATABASE_URL": mig_url.render_as_string(hide_password=False)}
    cwd = os.path.dirname(os.path.dirname(__file__))

    def alembic(*args):
        proc = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=cwd, env=env,
                              capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, proc.stderr

    await asyncio.to_thread(alembic, "upgrade", "0005")
    conn = await asyncpg.connect(
        user=url.username, password=url.password, host=url.host,
        port=url.port or 5432, database=MIG_DB,
    )
    try:
        uid = await conn.fetchval(
            "INSERT INTO users (id, name, username, password_hash, role) "
            "VALUES (gen_random_uuid(), 'Ira Teacher', 'ira', 'x', 'candidate') RETURNING id"
        )
        sid = await conn.fetchval(
            "INSERT INTO sessions (id, user_id, phase, status) "
            "VALUES (gen_random_uuid(), $1, 3, 'interview_complete') RETURNING id", uid)
        types = ["resume_targeted_md", "resume_targeted_docx", "cover_letter_md",
                 "cover_letter_docx", "resume", "resume_md", "score_card"]
        for t in types:
            await conn.execute(
                "INSERT INTO deliverables (id, session_id, type, filename, file_path) "
                "VALUES (gen_random_uuid(), $1, $2, 'f', '/x')", sid, t)
        await asyncio.to_thread(alembic, "upgrade", "head")
        rows = dict(await conn.fetch("SELECT type, kind FROM deliverables WHERE session_id=$1", sid))
    finally:
        await conn.close()
    assert {t: rows[t] for t in types[:4]} == {t: "targeted" for t in types[:4]}
    assert {rows[t] for t in types[4:]} == {"base"}
