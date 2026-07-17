from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    display_name: str
    email: str | None = None


class UserRead(BaseModel):
    id: UUID
    display_name: str
    email: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HouseholdMembershipCreate(BaseModel):
    user_id: UUID
    role: str = "member"


class HouseholdMembershipRead(BaseModel):
    id: UUID
    household_id: UUID
    user_id: UUID
    role: str
    created_at: datetime
    user: UserRead | None = None

    model_config = ConfigDict(from_attributes=True)
