"""Entities for the Alfen Modbus integration."""

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from . import AlfenModbusHub


class AlfenEntity(Entity):
    """Representation of an Alfen Modbus entity."""

    # _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hub: AlfenModbusHub,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the Alfen Modbus entity."""
        self._hub = hub
        self._attr_device_info = device_info

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hub.async_add_alfen_sensor(self._modbus_data_updated)

    async def async_will_remove_from_hass(self) -> None:
        """Remove callbacks."""
        self._hub.async_remove_alfen_sensor(self._modbus_data_updated)

    @callback
    def _modbus_data_updated(self) -> None:
        """Handle updated data from the hub."""
        self.async_write_ha_state()
