from collections.abc import Sequence

from industrial_agent.schemas.device import SyntheticDeviceRead

_DEVICES: tuple[SyntheticDeviceRead, ...] = (
    SyntheticDeviceRead(
        id="AOI-WAFER-01", name="AOI Wafer Inspector 01", category="inspection"
    ),
    SyntheticDeviceRead(id="ETCH-CHAMBER-02", name="Etch Chamber 02", category="etch"),
    SyntheticDeviceRead(
        id="LITHO-TRACK-01", name="Lithography Track 01", category="lithography"
    ),
)


class SyntheticDeviceNotFoundError(Exception):
    pass


def list_synthetic_devices() -> Sequence[SyntheticDeviceRead]:
    return _DEVICES


def get_synthetic_device(device_id: str) -> SyntheticDeviceRead:
    for device in _DEVICES:
        if device.id == device_id:
            return device
    raise SyntheticDeviceNotFoundError(device_id)
