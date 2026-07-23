from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


class CapabilitiesRead(BaseModel):
    admin_tools_enabled: bool
    fintrack_import_enabled: bool


@router.get("", response_model=CapabilitiesRead)
def get_capabilities(settings: Settings = Depends(get_settings)) -> CapabilitiesRead:
    return CapabilitiesRead(
        admin_tools_enabled=settings.enable_admin_tools,
        fintrack_import_enabled=settings.enable_admin_tools and settings.import_root is not None,
    )
