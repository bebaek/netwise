from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    AccountKind,
    AnnualTaxRecord,
    Household,
    IncomeSource,
    ProjectionSettings,
    ProjectionTransfer,
    SpendingItem,
)
from app.db.session import get_db
from app.schemas.planning import (
    AnnualTaxRecordCreate,
    AnnualTaxRecordRead,
    IncomeSourceCreate,
    IncomeSourceRead,
    ProjectionSettingsRead,
    ProjectionSettingsUpsert,
    ProjectionTransferCreate,
    ProjectionTransferRead,
    SpendingItemCreate,
    SpendingItemRead,
    SpendingItemUpdate,
)

router = APIRouter(tags=["planning"])


def _validate_asset_account(
    db: Session, household_id: UUID, account_id: UUID | None, label: str
) -> None:
    if account_id is None:
        return
    account = db.get(Account, account_id)
    if account is None or account.household_id != household_id or account.account_kind != AccountKind.asset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} must be an asset account in the household",
        )


@router.post(
    "/income-sources",
    response_model=IncomeSourceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_income_source(
    payload: IncomeSourceCreate,
    db: Session = Depends(get_db),
) -> IncomeSource:
    if db.get(Household, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    _validate_asset_account(db, payload.household_id, payload.deposit_account_id, "Deposit account")

    income_source = IncomeSource(**payload.model_dump())
    db.add(income_source)
    db.commit()
    db.refresh(income_source)
    return income_source


@router.post(
    "/projection-transfers",
    response_model=ProjectionTransferRead,
    status_code=status.HTTP_201_CREATED,
)
def create_projection_transfer(
    payload: ProjectionTransferCreate,
    db: Session = Depends(get_db),
) -> ProjectionTransfer:
    if db.get(Household, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    _validate_asset_account(db, payload.household_id, payload.from_account_id, "Source account")
    _validate_asset_account(db, payload.household_id, payload.to_account_id, "Destination account")
    if payload.from_account_id == payload.to_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination accounts must be different",
        )
    if payload.end_date is not None and payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be on or after start date",
        )

    projection_transfer = ProjectionTransfer(**payload.model_dump())
    db.add(projection_transfer)
    db.commit()
    db.refresh(projection_transfer)
    return projection_transfer


@router.get("/projection-transfers", response_model=list[ProjectionTransferRead])
def list_projection_transfers(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> list[ProjectionTransfer]:
    return list(
        db.scalars(
            select(ProjectionTransfer)
            .where(ProjectionTransfer.household_id == household_id)
            .order_by(ProjectionTransfer.name, ProjectionTransfer.created_at)
        ).all()
    )


@router.delete(
    "/projection-transfers/{projection_transfer_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_projection_transfer(
    projection_transfer_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    projection_transfer = db.get(ProjectionTransfer, projection_transfer_id)
    if projection_transfer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Projection transfer not found"
        )
    db.delete(projection_transfer)
    db.commit()


@router.post(
    "/spending-items",
    response_model=SpendingItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_spending_item(
    payload: SpendingItemCreate,
    db: Session = Depends(get_db),
) -> SpendingItem:
    if db.get(Household, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    spending_item = SpendingItem(**payload.model_dump())
    spending_item.name = spending_item.name.strip()
    spending_item.category = spending_item.category.strip().lower()
    if not spending_item.name or not spending_item.category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spending item name and category are required",
        )
    db.add(spending_item)
    db.commit()
    db.refresh(spending_item)
    return spending_item


@router.get("/spending-items", response_model=list[SpendingItemRead])
def list_spending_items(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> list[SpendingItem]:
    return list(
        db.scalars(
            select(SpendingItem)
            .where(SpendingItem.household_id == household_id)
            .order_by(SpendingItem.category, SpendingItem.name, SpendingItem.created_at)
        ).all()
    )


@router.patch("/spending-items/{spending_item_id}", response_model=SpendingItemRead)
def update_spending_item(
    spending_item_id: UUID,
    payload: SpendingItemUpdate,
    db: Session = Depends(get_db),
) -> SpendingItem:
    spending_item = db.get(SpendingItem, spending_item_id)
    if spending_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spending item not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("annual_amount") is None and "annual_amount" in values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Annual amount cannot be null"
        )
    for field, value in values.items():
        if field == "name" and value is not None:
            value = value.strip()
            if not value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Spending item name is required",
                )
        elif field == "category" and value is not None:
            value = value.strip().lower()
            if not value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Spending item category is required",
                )
        setattr(spending_item, field, value)
    db.commit()
    db.refresh(spending_item)
    return spending_item


@router.delete("/spending-items/{spending_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_spending_item(
    spending_item_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    spending_item = db.get(SpendingItem, spending_item_id)
    if spending_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spending item not found")
    db.delete(spending_item)
    db.commit()


@router.get("/projection-settings/{household_id}", response_model=ProjectionSettingsRead)
def get_projection_settings(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> ProjectionSettings:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    projection_settings = db.scalars(
        select(ProjectionSettings).where(ProjectionSettings.household_id == household_id)
    ).first()
    if projection_settings is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projection settings not found")
    return projection_settings


@router.put("/projection-settings/{household_id}", response_model=ProjectionSettingsRead)
def upsert_projection_settings(
    household_id: UUID,
    payload: ProjectionSettingsUpsert,
    db: Session = Depends(get_db),
) -> ProjectionSettings:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    _validate_asset_account(db, household_id, payload.spending_account_id, "Spending account")
    _validate_asset_account(db, household_id, payload.tax_account_id, "Tax account")

    projection_settings = db.scalars(
        select(ProjectionSettings).where(ProjectionSettings.household_id == household_id)
    ).first()
    if projection_settings is None:
        projection_settings = ProjectionSettings(household_id=household_id)
        db.add(projection_settings)

    for field, value in payload.model_dump().items():
        setattr(projection_settings, field, value)

    db.commit()
    db.refresh(projection_settings)
    return projection_settings


@router.get("/income-sources", response_model=list[IncomeSourceRead])
def list_income_sources(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> list[IncomeSource]:
    return list(
        db.scalars(
            select(IncomeSource)
            .where(IncomeSource.household_id == household_id)
            .order_by(IncomeSource.name)
        ).all()
    )


@router.get("/income-sources/{income_source_id}", response_model=IncomeSourceRead)
def get_income_source(
    income_source_id: UUID,
    db: Session = Depends(get_db),
) -> IncomeSource:
    income_source = db.get(IncomeSource, income_source_id)
    if income_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income source not found")
    return income_source


@router.post(
    "/annual-tax-records",
    response_model=AnnualTaxRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def create_annual_tax_record(
    payload: AnnualTaxRecordCreate,
    db: Session = Depends(get_db),
) -> AnnualTaxRecord:
    if db.get(Household, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    tax_record = AnnualTaxRecord(**payload.model_dump())
    db.add(tax_record)
    db.commit()
    db.refresh(tax_record)
    return tax_record


@router.get("/annual-tax-records", response_model=list[AnnualTaxRecordRead])
def list_annual_tax_records(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> list[AnnualTaxRecord]:
    return list(
        db.scalars(
            select(AnnualTaxRecord)
            .where(AnnualTaxRecord.household_id == household_id)
            .order_by(AnnualTaxRecord.tax_year.desc())
        ).all()
    )


@router.get("/annual-tax-records/{tax_record_id}", response_model=AnnualTaxRecordRead)
def get_annual_tax_record(
    tax_record_id: UUID,
    db: Session = Depends(get_db),
) -> AnnualTaxRecord:
    tax_record = db.get(AnnualTaxRecord, tax_record_id)
    if tax_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax record not found")
    return tax_record
