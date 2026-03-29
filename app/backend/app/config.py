from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://resume:resume@db:5432/resume_chat"
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    ADMIN_PASSWORD: str = "admin"
    ANTHROPIC_API_KEY: str = ""
    SYSTEM_DIR: str = "/app/system"
    PROFILES_DIR: str = "/app/profiles"
    TEMPLATES_DIR: str = "/app/templates"
    DELIVERABLES_DIR: str = "/app/deliverables"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
