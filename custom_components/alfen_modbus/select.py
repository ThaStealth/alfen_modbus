import logging
from typing import Optional, Dict, Any

from .const import (
    DOMAIN,
    ATTR_MANUFACTURER,
    CONTROL_PHASE,
    CONTROL_PHASE_MODES,
)

from homeassistant.const import CONF_NAME
from homeassistant.components.select import (
    PLATFORM_SCHEMA,
    SelectEntity,
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

    # If a meter is available add export control
    for select_info in CONTROL_PHASE:
        select = AlfenSelect(
            hub_name,
            hub,
            device_info,
            1,
            select_info[0],
            select_info[1],
            select_info[2],
            select_info[3],
        )
        entities.append(select)

    # If a second socket is available, add the controls
    if hub.has_socket_2:
        for select_info in CONTROL_PHASE:
            select = AlfenSelect(
                hub_name,
                hub,
                device_info,
                2,
                select_info[0],
                select_info[1],
                select_info[2],
                select_info[3],
            )
            entities.append(select)    

    async_add_entities(entities)
    return True

def get_key(my_dict, search):
    for k, v in my_dict.items():
        if v == search:
            return k
    return None

class AlfenSelect(SelectEntity):
    """Representation of an Alfen Modbus select."""

    def __init__(self,
                 platform_name,
                 hub,
                 device_info,
                 socket,
                 name,
                 key,
                 register,
                 options
    ) -> None:
        """Initialize the selector."""
        self._platform_name = platform_name
        self._hub = hub
        self._device_info = device_info
        self._name = name+str(socket)
        self._socket = socket
        self._key = key+str(socket)
        self._register = register
        self._option_dict = options
        self._attr_device_info = device_info
        self._attr_options = list(options.values())

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hub.async_add_alfen_sensor(self._modbus_data_updated)

    async def async_will_remove_from_hass(self) -> None:
        self._hub.async_remove_alfen_sensor(self._modbus_data_updated)

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
    def current_option(self) -> str:
        if self._key in self._hub.data:
            return self._hub.data[self._key]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        new_mode = get_key(self._option_dict, option)
        payload = self._hub._client.convert_to_registers(int(new_mode), data_type=self._hub._client.DATATYPE.UINT16, word_order="big")                   
        self._hub.write_registers(unit=self._socket, address=self._register, payload=payload)       
        self._hub.data[self._key] = option
        self.async_write_ha_state()

