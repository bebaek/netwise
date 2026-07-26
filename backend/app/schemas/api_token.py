from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ApiTokenScope = Literal["finance:read", "projections:run"]


class ApiTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    household_id: UUID
    scopes: list[ApiTokenScope] = Field(default_factory=lambda: ["finance:read"])
    expires_in_days: int = Field(default=90, ge=1, le=365)


class ApiTokenRead(BaseModel):
    id: UUID
    name: str
    household_id: UUID
    token_prefix: str
    scopes: list[ApiTokenScope]
    expires_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiTokenCreated(ApiTokenRead):
    token: str
