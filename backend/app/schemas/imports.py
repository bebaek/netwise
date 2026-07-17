from uuid import UUID

from pydantic import BaseModel, Field


class FintrackImportCreate(BaseModel):
    household_id: UUID
    data_dir: str
    currency: str = Field(default="USD", min_length=3, max_length=3)
    dry_run: bool = False


class FintrackAssetImportRead(BaseModel):
    name: str
    kind: str
    account_id: UUID | None
    liability_account_id: UUID | None
    accounts_created: int
    snapshots_created: int
    snapshots_updated: int
    events_created: int
    real_estate_profiles_created: int
    mortgage_profiles_created: int
    warnings: list[str]


class FintrackImportRead(BaseModel):
    household_id: UUID
    data_dir: str
    dry_run: bool
    accounts_created: int
    snapshots_created: int
    snapshots_updated: int
    events_created: int
    real_estate_profiles_created: int
    mortgage_profiles_created: int
    assets: list[FintrackAssetImportRead]
