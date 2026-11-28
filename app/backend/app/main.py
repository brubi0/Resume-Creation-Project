import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.auth import hash_password
from app.config import settings
from app.database import async_session, engine
from app.models import Base, User
from app.routers import admin_router, auth_router, candidate_router, deliverables_router


log = logging.getLogger("resume.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.JWT_SECRET == "change-me-in-production":
        log.warning("JWT_SECRET is still the default value; set a real secret")
    if settings.ADMIN_PASSWORD == "admin":
        log.warning("ADMIN_PASSWORD is still the default value; set a real password")

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

_FIELD_LABELS = {
    "content": "Message",
    "job_description": "Job description",
    "posting_text": "Posting text",
    "company": "Company",
    "role": "Role",
    "name": "Name",
}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Friendly string `detail` (the frontend shows it as-is); never echoes the input."""
    message = "Some of the information sent was invalid."
    for err in exc.errors():
        if err.get("type") == "string_too_long":
            field = str(err["loc"][-1])
            limit = (err.get("ctx") or {}).get("max_length")
            label = _FIELD_LABELS.get(field, "That field")
            message = f"{label} is too long (the limit is {limit:,} characters)."
            break
    return JSONResponse(status_code=422, content={"detail": message, "message": message})


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
