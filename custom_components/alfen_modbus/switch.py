"""Switch platform for Alfen Modbus."""
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME

from . import AlfenConfigEntry
from .const import (
    ATTR_MANUFACTURER,
    CONTROL_SLAVE_MAX_CURRENT,
    DOMAIN,
    MAX_CURRENT_REGISTER,
    MAX_CURRENT_S,
)
from .entity import AlfenEntity

_LOGGER = logging.getLogger(__name__)

_FALLBACK_MAX_CURRENT = CONTROL_SLAVE_MAX_CURRENT[0][4]["max"]


async def async_setup_entry(hass, entry: AlfenConfigEntry, async_add_entities) -> None:
    """Set up Alfen switches."""
    hub_name = entry.data[CONF_NAME]
    hub = entry.runtime_data

    device_info = {
        "identifiers": {(DOMAIN, hub_name)},
        "name": hub_name,
        "manufacturer": ATTR_MANUFACTURER,
        "model": hub.data.get("platformType", "Unknown"),
        "sw_version": hub.data.get("firmwareVersion", "Unknown"),
    }

    sockets = [1, 2] if hub.has_socket_2 else [1]
    entities = [
        AlfenChargerEnabledSwitch(hub_name, hub, device_info, socket)
        for socket in sockets
    ]

    async_add_entities(entities)
    return True


class AlfenChargerEnabledSwitch(AlfenEntity, SwitchEntity):
    """Enable/disable charging via the socket's max-current setpoint.

    Alfen's Modbus table has no dedicated enable/disable coil, so this
    reuses the max-current register (1210): off writes 0 A, on restores
    the station's currently allowed max current (actualMaxCurrent).
    """

    _attr_has_entity_name = True

    def __init__(self, platform_name, hub, device_info, socket: int) -> None:
        """Initialize the switch."""
        super().__init__(hub, device_info)
        self._platform_name = platform_name
        self._socket = socket
        self._key = MAX_CURRENT_S + str(socket)
        if hub.has_socket_2:
            self._attr_translation_key = "charger_enabled_socket"
            self._attr_translation_placeholders = {"socket_number": socket}
        else:
            self._attr_translation_key = "charger_enabled"

    @property
    def unique_id(self) -> str | None:
        return f"{self._platform_name}_socket_{self._socket}_chargerEnabled"

    @property
    def is_on(self) -> bool | None:
        if self._key in self._hub.data:
            return self._hub.data[self._key] > 0
        return None

    async def _write_max_current(self, value: float) -> None:
        payload = self._hub._client.convert_to_registers(
            float(value), data_type=self._hub._client.DATATYPE.FLOAT32, word_order="big"
        )
        await self._hub.write_registers(
            unit=self._socket, address=MAX_CURRENT_REGISTER, payload=payload
        )
        self._hub.data[self._key] = value
        self.hass.async_create_task(self._hub.async_refresh_modbus_data())
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Enable charging at the station's currently allowed max current."""
        max_current = self._hub.data.get(
            "socket_" + str(self._socket) + "_actualMaxCurrent", _FALLBACK_MAX_CURRENT
        )
        await self._write_max_current(max_current)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable charging by setting the max current to 0 A."""
        await self._write_max_current(0)
