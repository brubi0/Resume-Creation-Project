import uuid
from datetime import datetime

from pydantic import BaseModel


# --- Auth ---


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    username: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Admin: Candidates ---


class CandidateCreate(BaseModel):
    name: str
    password: str


class CandidateListItem(BaseModel):
    id: uuid.UUID
    name: str
    username: str
    created_at: datetime
    session_id: uuid.UUID | None = None
    session_status: str | None = None
    session_phase: int | None = None

    model_config = {"from_attributes": True}


# --- Chat ---


class MessageSend(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    phase: int
    created_at: datetime

    model_config = {"from_attributes": True}


class JobDescriptionUpdate(BaseModel):
    job_description: str


class SessionResponse(BaseModel):
    id: uuid.UUID
    phase: int
    experience_level: str | None
    profile_slug: str | None
    job_description: str | None
    resume_text: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatStatusResponse(BaseModel):
    phase: int
    experience_level: str | None
    profile_slug: str | None
    job_description: str | None
    resume_text: str | None
    status: str


# --- Deliverables ---


class DeliverableResponse(BaseModel):
    id: uuid.UUID
    type: str
    filename: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Profiles ---


class ProfileItem(BaseModel):
    slug: str
    name: str
    industry: str = ""
    target_roles: str = ""


class ProfileSelect(BaseModel):
    profile_slug: str
