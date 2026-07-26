from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectionScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    source_scenario_id: UUID | None = None


class ProjectionScenarioDuplicate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class ProjectionScenarioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class ProjectionScenarioAccountAssumptionUpdate(BaseModel):
    expected_annual_yield: Decimal | None = Field(
        default=None, ge=-1, max_digits=8, decimal_places=6
    )
    liquidation_expense_rate: Decimal | None = Field(
        default=None, ge=0, lt=1, max_digits=8, decimal_places=6
    )


class ProjectionScenarioAccountAssumptionRead(BaseModel):
    id: UUID
    scenario_id: UUID
    household_id: UUID
    account_id: UUID
    expected_annual_yield: Decimal | None
    liquidation_expense_rate: Decimal | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectionScenarioPropertyAssumptionUpdate(BaseModel):
    expected_appreciation_rate: Decimal | None = Field(
        default=None, ge=-1, max_digits=8, decimal_places=6
    )
    rent_growth_rate: Decimal | None = Field(
        default=None, ge=0, lt=1, max_digits=8, decimal_places=6
    )
    vacancy_rate: Decimal | None = Field(
        default=None, ge=0, lt=1, max_digits=8, decimal_places=6
    )


class ProjectionScenarioPropertyAssumptionRead(BaseModel):
    id: UUID
    scenario_id: UUID
    household_id: UUID
    property_account_id: UUID
    expected_appreciation_rate: Decimal | None
    rent_growth_rate: Decimal | None
    vacancy_rate: Decimal | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectionScenarioRead(BaseModel):
    id: UUID
    household_id: UUID
    name: str
    description: str | None
    is_baseline: bool
    created_from_scenario_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
