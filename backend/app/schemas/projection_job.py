from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectionJobRequest(BaseModel):
    scenario_id: UUID | None = None
    start_year: int
    end_year: int
    annual_spending: Decimal | None = None
    spending_inflation_rate: Decimal | None = None
    spending_account_id: UUID | None = None
    tax_account_id: UUID | None = None
    interval: Literal["annual", "quarterly", "monthly"] = "annual"


class ProjectionJobRead(BaseModel):
    id: UUID
    household_id: UUID
    scenario_id: UUID
    status: Literal["queued", "running", "completed", "failed", "stale"]
    cached: bool = False
    result: dict[str, Any] | None = None
    error_code: str | None = None
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None


class ProjectionJobList(BaseModel):
    jobs: list[ProjectionJobRead] = Field(default_factory=list)
