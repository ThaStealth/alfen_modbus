"""Binary sensor platform for Alfen Modbus."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import callback

from .const import DOMAIN, DEFAULT_MANUFACTURER

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_ENTITY_DESCRIPTORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="backoffice",
        translation_key="backoffice",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

SOCKET_BINARY_SENSOR_ENTITY_DESCRIPTORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="carconnected",
        translation_key="carconnected",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    BinarySensorEntityDescription(
        key="carcharging",
        translation_key="carcharging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Alfen binary sensors."""
    hub_name = entry.data[CONF_NAME]
    hub = hass.data[DOMAIN][name]["hub"]
    device_info = {
        "identifiers": {(DOMAIN, hub_name)},
        "serial_number": hub.data.get("serial", None),
        "manufacturer": hub.data.get("manufacturer", DEFAULT_MANUFACTURER),
        "model": hub.data.get("platformType", None),
        "sw_version": hub.data.get("firmwareVersion", None),
    }

    sockets = [1, 2] if hub.has_socket_2 else [1]
    entities: list[AlfenBinarySensor] = []
    entities.extend(
        AlfenBinarySensor(
            hub_name,
            hub,
            device_info,
            entity_description,
            None,
        )
        for entity_description in BINARY_SENSOR_ENTITY_DESCRIPTORS
    )
    entities.extend(
        AlfenBinarySensor(
            name,
            hub_hub,
            device_info,
            entity_description,
            socket,
        )
        for entity_description in SOCKET_BINARY_SENSOR_ENTITY_DESCRIPTORS
        for socket in sockets
    )
    async_add_entities(entities)


class AlfenBinarySensor(BinarySensorEntity):
    """Representation of an Alfen Modbus binary sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        name,
        hub,
        device_info,
        entity_description: BinarySensorEntityDescription,
        socket: int | None,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = entity_description
        self._hub = hub
        if socket is not None:
            self.key = f"socket_{socket}_{entity_description.key}"
            self._attr_translation_placeholders = {
                "socket_number": socket,
            }
        else:
            self.key = entity_description.key
        self._attr_unique_id = f"{name}_{self.key}"
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

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if self.key in self._hub.data:
            return self._hub.data[self.key] == 1
        return False
