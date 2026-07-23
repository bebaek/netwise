from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Household
from app.db.session import get_db
from app.importers.fintrack import FintrackImportError, import_fintrack_directory
from app.schemas.imports import FintrackImportCreate, FintrackImportRead

router = APIRouter(prefix="/imports", tags=["imports"])


def require_admin_tools_enabled(settings: Settings = Depends(get_settings)) -> None:
    if not settings.enable_admin_tools:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin tools are disabled")


def resolve_import_directory(data_dir: str, settings: Settings) -> Path:
    if settings.import_root is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FinTrack import root is not configured",
        )

    root = settings.import_root.expanduser().resolve()
    if not root.is_dir():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configured FinTrack import root is unavailable",
        )

    requested = Path(data_dir).expanduser()
    resolved = (requested if requested.is_absolute() else root / requested).resolve()
    if not resolved.is_relative_to(root):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FinTrack data directory must be inside the configured import root",
        )
    return resolved


@router.post("/fintrack", response_model=FintrackImportRead, status_code=status.HTTP_201_CREATED)
def import_fintrack(
    payload: FintrackImportCreate,
    _: None = Depends(require_admin_tools_enabled),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if db.get(Household, payload.household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found")

    try:
        return import_fintrack_directory(
            db,
            household_id=payload.household_id,
            data_dir=resolve_import_directory(payload.data_dir, settings),
            currency=payload.currency,
            dry_run=payload.dry_run,
        )
    except FintrackImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
