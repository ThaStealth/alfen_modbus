import logging
from typing import Optional, Dict, Any

from .const import (
    DOMAIN,
    ATTR_MANUFACTURER,
    CONTROL_SLAVE_MAX_CURRENT,
)

from homeassistant.const import CONF_NAME
from homeassistant.components.number import (
    PLATFORM_SCHEMA,
    NumberEntity,
)

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    hub_name = entry.data[CONF_NAME]
    hub = hass.data[DOMAIN][hub_name]["hub"]

    device_info = {
        "identifiers": {(DOMAIN, hub_name)},
        "name": hub_name,
        "manufacturer": ATTR_MANUFACTURER,
    }

    entities = []

    for number_info in CONTROL_SLAVE_MAX_CURRENT:
        number = AlfenNumber(
            hub_name,
            hub,
            device_info,
            1,
            number_info[0],
            number_info[1],
            number_info[2],
            number_info[3],
            number_info[4],
        )
        entities.append(number)
        
    if hub.has_socket_2:
        for number_info in CONTROL_SLAVE_MAX_CURRENT:
            number = AlfenNumber(
                hub_name,
                hub,
                device_info,
                2,
                number_info[0],
                number_info[1],
                number_info[2],
                number_info[3],
                number_info[4],
            )
            entities.append(number)

    async_add_entities(entities)
    return True

class AlfenNumber(NumberEntity):
    """Representation of an Alfen Modbus number."""

    def __init__(self,
                 platform_name,
                 hub,
                 device_info,
                 socket,
                 name,
                 key,
                 register,
                 fmt,
                 attrs
    ) -> None:
        """Initialize the selector."""
        self._platform_name = platform_name
        self._hub = hub
        self._device_info = device_info
        self._name = name+str(socket)
        self._socket = socket
        self._key = key+str(socket)
        self._register = register
        self._fmt = fmt
        self._attr_device_info = device_info
        self._attr_native_min_value = attrs["min"]
        self._attr_native_max_value = attrs["max"]
        if "unit" in attrs.keys():
            self._attr_native_unit_of_measurement = attrs["unit"]

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hub.async_add_alfen_sensor(self._modbus_data_updated,self.update_value)

    async def async_will_remove_from_hass(self) -> None:
        self._hub.async_remove_alfen_sensor(self._modbus_data_updated,self.update_value)

    @callback
    def _modbus_data_updated(self) -> None:
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._platform_name} ({self._name})"

    @property
    def unique_id(self) -> Optional[str]:
        return f"{self._platform_name}_{self._key}"

    @property
    def should_poll(self) -> bool:
        """Data is delivered by the hub"""
        return False

    @property
    def native_value(self) -> float:
        if self._key in self._hub.data:
            return self._hub.data[self._key]

    def update_value(self):
        value = self._hub.data[self._key]
        if "MAX_CURRENT_S"+str(self._socket) in self._hub.data:
            self._attr_native_max_value = self._hub.data["MAX_CURRENT_S"+str(self._socket)]
        _LOGGER.debug("Updating value to: %f",value)

        if self._fmt == "u":
            payload = self._hub._client.convert_to_registers(int(value), data_type=self._hub._client.DATATYPE.UINT16, word_order="big")
        elif self._fmt == "f":
            payload = self._hub._client.convert_to_registers(float(value), data_type=self._hub._client.DATATYPE.FLOAT32, word_order="big")

        self._hub.write_registers(unit=self._socket, address=self._register, payload=payload)


    async def async_set_native_value(self, value: float) -> None:
        """Change the selected value."""
        self._hub.data[self._key] = value
        self.update_value()       
        self.async_write_ha_state()
