from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.auth import hash_password
from app.config import settings
from app.database import async_session, engine
from app.models import Base, User
from app.routers import admin_router, auth_router, candidate_router, deliverables_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (use alembic in production, this is a fallback)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure admin user exists
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                name="Admin",
                username="admin",
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin)
            await db.commit()

    yield

    await engine.dispose()


app = FastAPI(title="Resume Chat", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(admin_router.router, prefix="/api/admin", tags=["admin"])
app.include_router(candidate_router.router, prefix="/api/chat", tags=["chat"])
app.include_router(
    deliverables_router.router, prefix="/api/deliverables", tags=["deliverables"]
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
