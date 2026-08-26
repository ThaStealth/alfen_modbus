import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_NAME, UnitOfEnergy, UnitOfPower

from . import AlfenConfigEntry
from .const import (
    ATTR_MANUFACTURER,
    AVAILABILITY_MODES,
    BOOLEAN_EXPLAINED,
    CONTROL_PHASE_MODES,
    DOMAIN,
    ENUM_SENSOR_KEYS,
    METER_STATE_MODES,
    METER_TYPE,
    SCN_SENSOR_TYPES,
    SENSOR_TYPES,
    SOCKET_SENSOR_TYPES,
)
from .entity import AlfenEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry: AlfenConfigEntry, async_add_entities):
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
    for sensor_info in SENSOR_TYPES.values():
        sensor = AlfenSensor(
            hub_name,
            hub,
            device_info,
            sensor_info[0],
            sensor_info[1],
            sensor_info[2],
            sensor_info[3],
        )
        entities.append(sensor)

    if hub.read_scn:
        for meter_sensor_info in SCN_SENSOR_TYPES.values():
            sensor = AlfenSensor(
                hub_name,
                hub,
                device_info,
                meter_sensor_info[0],
                meter_sensor_info[1],
                meter_sensor_info[2],
                meter_sensor_info[3],
            )
            entities.append(sensor)

    sockets = [1, 2] if hub.has_socket_2 else [1]
    for socket in sockets:
        for meter_sensor_info in SOCKET_SENSOR_TYPES.values():
            translation_key, key_template, unit, icon = meter_sensor_info
            sensor = AlfenSensor(
                hub_name,
                hub,
                device_info,
                translation_key,
                key_template.format(socket=socket),
                unit,
                icon,
                socket=socket,
            )
            entities.append(sensor)

    async_add_entities(entities)
    return True


class AlfenSensor(AlfenEntity, SensorEntity):
    """Representation of an Alfen Modbus sensor."""

    _attr_has_entity_name = True

    def __init__(self, platform_name, hub, device_info, translation_key, key, unit, icon, socket: int | None = None):
        """Initialize the sensor."""
        super().__init__(hub, device_info)
        self._platform_name = platform_name
        self._key = key
        if socket is not None and hub.has_socket_2:
            self._attr_translation_key = f"{translation_key}_socket"
            self._attr_translation_placeholders = {"socket_number": socket}
        else:
            self._attr_translation_key = translation_key
        self._unit_of_measurement = unit
        self._icon = icon
        self._device_info = device_info
        self._attr_state_class = SensorStateClass.MEASUREMENT
        if self._unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR or self._unit_of_measurement == UnitOfEnergy.WATT_HOUR:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_device_class = SensorDeviceClass.ENERGY
        if self._unit_of_measurement == UnitOfPower.WATT :
            self._attr_device_class = SensorDeviceClass.POWER
        if self._key in ENUM_SENSOR_KEYS:
            self._attr_state_class = None
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = ["on", "off"]

    @property
    def unique_id(self) -> str | None:
        return f"{self._platform_name}_{self._key}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the sensor icon."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._key in self._hub.data and self._hub.data[self._key] == self._hub.data[self._key]: #check for NaN
            if self._key in ["socket_1_meterType", "socket_2_meterType"] and self._hub.data[self._key] in METER_TYPE:
                return METER_TYPE[self._hub.data[self._key]]
            elif self._key in ["socket_1_meterstate", "socket_2_meterstate"] and self._hub.data[self._key] in METER_STATE_MODES:
                return METER_STATE_MODES[self._hub.data[self._key]]     
            elif self._key in ["socket_1_available", "socket_2_available"] and self._hub.data[self._key] in AVAILABILITY_MODES:
                return AVAILABILITY_MODES[self._hub.data[self._key]]   
            elif self._key in ENUM_SENSOR_KEYS and self._hub.data[self._key] in BOOLEAN_EXPLAINED:
                return "on" if BOOLEAN_EXPLAINED[self._hub.data[self._key]] else "off"
            elif self._key in ["socket_1_chargephases", "socket_2_chargephases"] and self._hub.data[self._key] in CONTROL_PHASE_MODES:
                return CONTROL_PHASE_MODES[self._hub.data[self._key]]  
            else:
                return self._hub.data[self._key]           

    @property
    def extra_state_attributes(self):         
        return None
