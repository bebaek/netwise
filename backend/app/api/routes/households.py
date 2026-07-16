from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Household
from app.db.session import get_db
from app.schemas.household import HouseholdCreate, HouseholdRead

router = APIRouter(prefix="/households", tags=["households"])


@router.post("", response_model=HouseholdRead, status_code=status.HTTP_201_CREATED)
def create_household(payload: HouseholdCreate, db: Session = Depends(get_db)) -> Household:
    household = Household(name=payload.name)
    db.add(household)
    db.commit()
    db.refresh(household)
    return household


@router.get("", response_model=list[HouseholdRead])
def list_households(db: Session = Depends(get_db)) -> list[Household]:
    return list(db.scalars(select(Household).order_by(Household.created_at)).all())


@router.get("/{household_id}", response_model=HouseholdRead)
def get_household(household_id: UUID, db: Session = Depends(get_db)) -> Household:
    household = db.get(Household, household_id)
    if household is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")
    return household
