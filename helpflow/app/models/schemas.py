from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict

Role = Literal["SUPPORT_AGENT", "SUPPORT_MANAGER", "ADMIN"]
ManagedRole = Literal["SUPPORT_AGENT", "SUPPORT_MANAGER"]
Priority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

class TicketCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=4, max_length=200)
    description: str = Field(min_length=8, max_length=4000)
    service_name: str = Field(min_length=2, max_length=100)
    priority: Priority = "MEDIUM"

class Ticket(BaseModel):
    id: int; title: str; description: str; service_name: str; priority: str; severity: str | None = None; status: str; created_at: datetime; updated_at: datetime

class AgentEvent(BaseModel):
    workflow_state: str; event_type: str; message: str; metadata: dict[str, Any] = {}; created_at: datetime

class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=256)
    admin_token: str = Field(default="", max_length=256)

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=256)
    role: ManagedRole = "SUPPORT_AGENT"

class UserPatch(BaseModel):
    role: Role | None = None
    is_active: bool | None = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=256)

class ApprovalDecision(BaseModel):
    decision_reason: str = Field(default="", max_length=2000)
