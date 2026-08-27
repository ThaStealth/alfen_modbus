import logging

from homeassistant.components.number import NumberEntity
from homeassistant.const import CONF_NAME

from . import AlfenConfigEntry
from .const import (
    ATTR_MANUFACTURER,
    CONTROL_SCN_MAX_CURRENT,
    CONTROL_SLAVE_MAX_CURRENT,
    DOMAIN,
    MAX_CURRENT_S,
    SCN_ACTUAL_MAX_CURRENT_L,
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

    if hub.has_scn:
        for scn_number_info in CONTROL_SCN_MAX_CURRENT:
            entities.append(
                AlfenSCNNumber(
                    hub_name,
                    hub,
                    device_info,
                    scn_number_info[0],
                    scn_number_info[1],
                    scn_number_info[2],
                    scn_number_info[3],
                    scn_number_info[4],
                )
            )

    async_add_entities(entities)
    return True

class AlfenNumber(AlfenEntity, NumberEntity):
    """Representation of an Alfen Modbus number."""

    _attr_has_entity_name = True

    def __init__(self,
                 platform_name,
                 hub,
                 device_info,
                 socket,
                 translation_key,
                 key,
                 register,
                 fmt,
                 attrs
    ) -> None:
        """Initialize the number."""
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
        self._fmt = fmt
        self._attr_native_min_value = attrs["min"]
        self._attr_native_max_value = attrs["max"]
        if "unit" in attrs:
            self._attr_native_unit_of_measurement = attrs["unit"]
        if "mode" in attrs:
            self._attr_mode = attrs["mode"]
        if "step" in attrs:
            self._attr_native_step = attrs["step"]

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hub.async_add_alfen_sensor(self._modbus_data_updated, self.update_value)

    async def async_will_remove_from_hass(self) -> None:
        self._hub.async_remove_alfen_sensor(self._modbus_data_updated, self.update_value)

    @property
    def unique_id(self) -> str | None:
        return f"{self._platform_name}_{self._key}"

    @property
    def native_value(self) -> float:
        if self._key in self._hub.data:
            return self._hub.data[self._key]

    async def update_value(self):
        if self._key not in self._hub.data:
            _LOGGER.debug("Key %s not in hub data, skipping update_value", self._key)
            return
        value = self._hub.data[self._key]
        
        # Use actualMaxCurrent (Register 1100) as the hard limit for the slider
        if "actualMaxCurrent" in self._hub.data:
            self._attr_native_max_value = self._hub.data["actualMaxCurrent"]
        elif MAX_CURRENT_S+str(self._socket) in self._hub.data:
             # Fallback to previous logic if actualMaxCurrent not available
            self._attr_native_max_value = self._hub.data[MAX_CURRENT_S+str(self._socket)]
            
        _LOGGER.debug("Updating value to: %f",value)

        if self._fmt == "u":
            payload = self._hub._client.convert_to_registers(int(value), data_type=self._hub._client.DATATYPE.UINT16, word_order="big")
        elif self._fmt == "f":
            payload = self._hub._client.convert_to_registers(float(value), data_type=self._hub._client.DATATYPE.FLOAT32, word_order="big")

        await self._hub.write_registers(unit=self._socket, address=self._register, payload=payload)


    async def async_set_native_value(self, value: float) -> None:
        """Change the selected value."""
        # Clamp value to actualMaxCurrent if available
        if "actualMaxCurrent" in self._hub.data:
            max_allowed = self._hub.data["actualMaxCurrent"]
            if value > max_allowed:
                _LOGGER.warning("Requested value %s exceeds max current %s, clamping.", value, max_allowed)
                value = max_allowed

        self._hub.data[self._key] = value
        await self.update_value()
        self.hass.async_create_task(self._hub.async_refresh_modbus_data())
        self.async_write_ha_state()


class AlfenSCNNumber(AlfenEntity, NumberEntity):
    """Representation of an Alfen Modbus SCN max-current-per-phase number.

    SCN registers live at the station's own Modbus address (unlike socket
    max current, which is written to the socket's slave address), so this
    doesn't reuse AlfenNumber's per-socket unit. It also does not auto-renew:
    unlike per-socket max current, enabling this is a deliberate takeover of
    SCN balancing, not a side effect of reading SCN telemetry, so the setpoint
    is written only when the user changes it and is left to lapse to the
    station's configured safe current otherwise.
    """

    _attr_has_entity_name = True

    def __init__(self,
                 platform_name,
                 hub,
                 device_info,
                 translation_key,
                 key,
                 phase,
                 register,
                 attrs
    ) -> None:
        """Initialize the number."""
        super().__init__(hub, device_info)
        self._platform_name = platform_name
        self._attr_translation_key = translation_key
        self._key = key
        self._actual_max_current_key = SCN_ACTUAL_MAX_CURRENT_L + phase
        self._register = register
        self._attr_native_min_value = attrs["min"]
        self._attr_native_max_value = attrs["max"]
        self._attr_native_unit_of_measurement = attrs["unit"]
        self._attr_mode = attrs["mode"]
        self._attr_native_step = attrs["step"]

    @property
    def unique_id(self) -> str | None:
        return f"{self._platform_name}_{self._key}"

    @property
    def native_max_value(self) -> float:
        return self._hub.data.get(self._actual_max_current_key, self._attr_native_max_value)

    @property
    def native_value(self) -> float | None:
        return self._hub.data.get(self._key)

    async def async_set_native_value(self, value: float) -> None:
        """Change the selected value."""
        payload = self._hub._client.convert_to_registers(
            float(value), data_type=self._hub._client.DATATYPE.FLOAT32, word_order="big"
        )
        await self._hub.write_registers(unit=self._hub._address, address=self._register, payload=payload)
        self._hub.data[self._key] = value
        self.hass.async_create_task(self._hub.async_refresh_modbus_data())
        self.async_write_ha_state()
