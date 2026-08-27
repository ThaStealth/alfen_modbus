"""Repairs support for the Alfen Modbus integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

ISSUE_NG9XX_FIRMWARE_OUTDATED = "ng9xx_firmware_outdated"

# NG9xx firmware below this resets the power budget to 0A when no car is
# connected (see README Known Issues); fixed in 6.4.0-4210.
_NG9XX_MIN_FIRMWARE = (6, 4, 0)


def _firmware_tuple(version: str) -> tuple[int, ...] | None:
    """Parse the leading dotted numeric part of a firmware string.

    E.g. "6.4.0-4210" -> (6, 4, 0). Returns None if it doesn't parse.
    """
    core = version.split("-", 1)[0]
    parts = core.split(".")
    if not parts or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def async_check_firmware(
    hass: HomeAssistant, entry_id: str, platform_type: str, firmware_version: str
) -> None:
    """Create or clear the outdated NG9xx firmware repair issue."""
    issue_id = f"{ISSUE_NG9XX_FIRMWARE_OUTDATED}_{entry_id}"

    if "NG9" not in platform_type.upper():
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    parsed = _firmware_tuple(firmware_version)
    if parsed is not None and parsed >= _NG9XX_MIN_FIRMWARE:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_NG9XX_FIRMWARE_OUTDATED,
        translation_placeholders={"firmware_version": firmware_version},
    )


def async_clear_firmware_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Remove the outdated-firmware issue, e.g. on unload."""
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_NG9XX_FIRMWARE_OUTDATED}_{entry_id}")
