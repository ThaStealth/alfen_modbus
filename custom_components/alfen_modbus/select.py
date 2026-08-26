import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_NAME

from . import AlfenConfigEntry
from .const import (
    ATTR_MANUFACTURER,
    CONTROL_PHASE,
    DOMAIN,
)
from .entity import AlfenEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry: AlfenConfigEntry, async_add_entities) -> None:
    hub_name = entry.data[CONF_NAME]
    hub = entry.runtime_data

    device_info = {
        "identifiers": {(DOMAIN, hub_name)},
        "name": hub_name,
        "manufacturer": ATTR_MANUFACTURER,
        "model": hub.data.get("platformType", "Unknown"),
        "sw_version": hub.data.get("firmwareVersion", "Unknown"),
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

class AlfenSelect(AlfenEntity, SelectEntity):
    """Representation of an Alfen Modbus select."""

    _attr_has_entity_name = True

    def __init__(self,
                 platform_name,
                 hub,
                 device_info,
                 socket,
                 translation_key,
                 key,
                 register,
                 options
    ) -> None:
        """Initialize the selector."""
        super().__init__(hub, device_info)
        self._platform_name = platform_name
        if hub.has_socket_2:
            self._attr_translation_key = f"{translation_key}_socket"
            self._attr_translation_placeholders = {"socket_number": socket}
        else:
            self._attr_translation_key = translation_key
        self._socket = socket
        self._key = key+str(socket)
        self._register = register
        self._option_dict = options
        self._attr_options = list(options.values())

    @property
    def unique_id(self) -> str | None:
        return f"{self._platform_name}_{self._key}"

    @property
    def current_option(self) -> str:
        if self._key in self._hub.data:
            return self._hub.data[self._key]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        new_mode = get_key(self._option_dict, option)
        payload = self._hub._client.convert_to_registers(int(new_mode), data_type=self._hub._client.DATATYPE.UINT16, word_order="big")                   
        await self._hub.write_registers(unit=self._socket, address=self._register, payload=payload)       
        self._hub.data[self._key] = option
        self.hass.async_create_task(self._hub.async_refresh_modbus_data())
        self.async_write_ha_state()
