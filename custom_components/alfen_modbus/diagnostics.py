"""Diagnostics support for the Alfen Modbus integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import AlfenConfigEntry

TO_REDACT = {CONF_HOST, "serial"}


def _json_safe(data: dict[str, Any]) -> dict[str, Any]:
    """Convert values the diagnostics JSON encoder can't handle as-is."""
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in data.items()
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AlfenConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub = entry.runtime_data

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "hub_data": async_redact_data(_json_safe(hub.data), TO_REDACT),
    }
