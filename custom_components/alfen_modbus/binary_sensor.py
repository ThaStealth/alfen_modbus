"""Binary sensor platform for Alfen Modbus."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_NAME, EntityCategory

from . import AlfenConfigEntry
from .const import DEFAULT_MANUFACTURER, DOMAIN
from .entity import AlfenEntity

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_ENTITY_DESCRIPTORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="backoffice",
        translation_key="backoffice",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

SCN_BINARY_SENSOR_ENTITY_DESCRIPTORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="scnMaxCurrentEnabled",
        translation_key="scn_max_current_enabled",
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
    BinarySensorEntityDescription(
        key="chargerenabled",
        translation_key="charger_enabled",
    ),
)

async def async_setup_entry(hass, entry: AlfenConfigEntry, async_add_entities) -> None:
    """Set up Alfen binary sensors."""
    hub_name = entry.data[CONF_NAME]
    hub = entry.runtime_data

    device_info = {
        "identifiers": {(DOMAIN, hub_name)},
        "name": hub_name,
        "serial_number": hub.data.get("serial", None),
        "manufacturer": DEFAULT_MANUFACTURER,
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
    if hub.read_scn:
        entities.extend(
            AlfenBinarySensor(
                hub_name,
                hub,
                device_info,
                entity_description,
                None,
            )
            for entity_description in SCN_BINARY_SENSOR_ENTITY_DESCRIPTORS
        )
    entities.extend(
        AlfenBinarySensor(
            hub_name,
            hub,
            device_info,
            entity_description,
            socket,
        )
        for entity_description in SOCKET_BINARY_SENSOR_ENTITY_DESCRIPTORS
        for socket in sockets
    )
    async_add_entities(entities)


class AlfenBinarySensor(AlfenEntity, BinarySensorEntity):
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
        super().__init__(hub, device_info)
        self.entity_description = entity_description
        if socket is not None:
            self.key = f"socket_{socket}_{entity_description.key}"
            if hub.has_socket_2:
                self._attr_translation_key = f"{entity_description.translation_key}_socket"
                self._attr_translation_placeholders = {
                    "socket_number": socket,
                }
        else:
            self.key = entity_description.key
        self._attr_unique_id = f"{name}_{self.key}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if self.key in self._hub.data:
            return self._hub.data[self.key] == 1
        return False
