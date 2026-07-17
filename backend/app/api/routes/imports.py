from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Household
from app.db.session import get_db
from app.importers.fintrack import FintrackImportError, import_fintrack_directory
from app.schemas.imports import FintrackImportCreate, FintrackImportRead

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/fintrack", response_model=FintrackImportRead, status_code=status.HTTP_201_CREATED)
def import_fintrack(payload: FintrackImportCreate, db: Session = Depends(get_db)):
    if db.get(Household, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    try:
        return import_fintrack_directory(
            db,
            household_id=payload.household_id,
            data_dir=payload.data_dir,
            currency=payload.currency,
            dry_run=payload.dry_run,
        )
    except FintrackImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
