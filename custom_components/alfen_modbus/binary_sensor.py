"""Binary sensor platform for Alfen Modbus."""
import logging
from typing import Optional, Dict, Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import DOMAIN, ATTR_MANUFACTURER
from .entity import AlfenEntity

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_TYPES = [
    ["Car Connected", "carconnected", BinarySensorDeviceClass.PLUG, "mdi:power-plug", "mdi:power-plug-off"],
    ["Car Charging", "carcharging", BinarySensorDeviceClass.BATTERY_CHARGING, "mdi:battery-charging", "mdi:battery-off"],
]


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Alfen binary sensors."""
    hub_name = entry.data[CONF_NAME]
    hub = hass.data[DOMAIN][hub_name]["hub"]

    device_info = {
        "identifiers": {(DOMAIN, hub_name)},
        "name": hub_name,
        "manufacturer": ATTR_MANUFACTURER,
        "model": hub.data.get("platformType", "Unknown"),
        "sw_version": hub.data.get("firmwareVersion", "Unknown"),
    }

    entities = []

    # Socket 1 binary sensors
    for sensor_info in BINARY_SENSOR_TYPES:
        sensor = AlfenBinarySensor(
            hub_name,
            hub,
            device_info,
            1,
            sensor_info[0],
            sensor_info[1],
            sensor_info[2],
            sensor_info[3],
            sensor_info[4],
        )
        entities.append(sensor)

    # Socket 2 binary sensors (if available)
    if hub.has_socket_2:
        for sensor_info in BINARY_SENSOR_TYPES:
            sensor = AlfenBinarySensor(
                hub_name,
                hub,
                device_info,
                2,
                sensor_info[0],
                sensor_info[1],
                sensor_info[2],
                sensor_info[3],
                sensor_info[4],
            )
            entities.append(sensor)

    async_add_entities(entities)
    return True


class AlfenBinarySensor(AlfenEntity, BinarySensorEntity):
    """Representation of an Alfen Modbus binary sensor."""

    def __init__(
        self,
        platform_name,
        hub,
        device_info,
        socket,
        name,
        key,
        device_class,
        icon_on,
        icon_off,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(hub, device_info)
        self._platform_name = platform_name
        self._socket = socket
        self._name = f"S{socket} {name}" if hub.has_socket_2 else name
        self._key = f"socket_{socket}_{key}"
        self._attr_device_class = device_class
        self._icon_on = icon_on
        self._icon_off = icon_off

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._platform_name} {self._name}"

    @property
    def unique_id(self) -> Optional[str]:
        """Return unique ID."""
        return f"{self._platform_name}_{self._key}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if self._key in self._hub.data:
            return self._hub.data[self._key] == 1
        return False

    @property
    def icon(self) -> str:
        """Return the icon based on state."""
        return self._icon_on if self.is_on else self._icon_off
