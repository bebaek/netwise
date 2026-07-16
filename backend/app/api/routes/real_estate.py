from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account, AccountKind, MortgageProfile, RealEstateProperty
from app.db.session import get_db
from app.schemas.real_estate import (
    MortgageProfileCreate,
    MortgageProfileRead,
    RealEstatePropertyCreate,
    RealEstatePropertyRead,
)

router = APIRouter(tags=["real-estate"])


@router.post(
    "/real-estate/properties",
    response_model=RealEstatePropertyRead,
    status_code=status.HTTP_201_CREATED,
)
def create_real_estate_property(
    payload: RealEstatePropertyCreate,
    db: Session = Depends(get_db),
) -> RealEstateProperty:
    account = db.get(Account, payload.account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if account.account_kind != AccountKind.asset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Real estate property must be linked to an asset account",
        )

    real_estate_property = RealEstateProperty(
        household_id=account.household_id,
        **payload.model_dump(),
    )
    db.add(real_estate_property)
    db.commit()
    db.refresh(real_estate_property)
    return real_estate_property


@router.get(
    "/real-estate/properties",
    response_model=list[RealEstatePropertyRead],
)
def list_real_estate_properties(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> list[RealEstateProperty]:
    return list(
        db.scalars(
            select(RealEstateProperty)
            .where(RealEstateProperty.household_id == household_id)
            .order_by(RealEstateProperty.created_at)
        ).all()
    )


@router.get(
    "/real-estate/properties/{property_id}",
    response_model=RealEstatePropertyRead,
)
def get_real_estate_property(
    property_id: UUID,
    db: Session = Depends(get_db),
) -> RealEstateProperty:
    real_estate_property = db.get(RealEstateProperty, property_id)
    if real_estate_property is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return real_estate_property


@router.post(
    "/mortgages",
    response_model=MortgageProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_mortgage_profile(
    payload: MortgageProfileCreate,
    db: Session = Depends(get_db),
) -> MortgageProfile:
    liability_account = db.get(Account, payload.liability_account_id)
    if liability_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liability account not found")
    if liability_account.account_kind != AccountKind.liability:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mortgage profile must be linked to a liability account",
        )

    if payload.property_account_id is not None:
        property_account = db.get(Account, payload.property_account_id)
        if property_account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property account not found")
        if property_account.household_id != liability_account.household_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Property account must belong to the same household",
            )
        if property_account.account_kind != AccountKind.asset:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Property account must be an asset account",
            )

    mortgage_profile = MortgageProfile(
        household_id=liability_account.household_id,
        **payload.model_dump(),
    )
    db.add(mortgage_profile)
    db.commit()
    db.refresh(mortgage_profile)
    return mortgage_profile


@router.get("/mortgages", response_model=list[MortgageProfileRead])
def list_mortgage_profiles(
    household_id: UUID,
    db: Session = Depends(get_db),
) -> list[MortgageProfile]:
    return list(
        db.scalars(
            select(MortgageProfile)
            .where(MortgageProfile.household_id == household_id)
            .order_by(MortgageProfile.created_at)
        ).all()
    )


@router.get("/mortgages/{mortgage_id}", response_model=MortgageProfileRead)
def get_mortgage_profile(
    mortgage_id: UUID,
    db: Session = Depends(get_db),
) -> MortgageProfile:
    mortgage_profile = db.get(MortgageProfile, mortgage_id)
    if mortgage_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mortgage profile not found")
    return mortgage_profile
