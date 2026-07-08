from fastapi import APIRouter

from industrial_agent.schemas.device import SyntheticDeviceRead
from industrial_agent.services.device import list_synthetic_devices

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[SyntheticDeviceRead])
def list_devices() -> list[SyntheticDeviceRead]:
    return list(list_synthetic_devices())
