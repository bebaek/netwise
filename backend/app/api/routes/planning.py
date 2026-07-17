from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account, AccountKind, AnnualTaxRecord, Household, IncomeSource
from app.db.session import get_db
from app.schemas.planning import (
    AnnualTaxRecordCreate,
    AnnualTaxRecordRead,
    IncomeSourceCreate,
    IncomeSourceRead,
)

router = APIRouter(tags=["planning"])


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
    if payload.deposit_account_id is not None:
        account = db.get(Account, payload.deposit_account_id)
        if (
            account is None
            or account.household_id != payload.household_id
            or account.account_kind != AccountKind.asset
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Deposit account must be an asset account in the household",
            )

    income_source = IncomeSource(**payload.model_dump())
    db.add(income_source)
    db.commit()
    db.refresh(income_source)
    return income_source


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
