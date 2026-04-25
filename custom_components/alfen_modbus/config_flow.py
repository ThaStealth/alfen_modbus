import ipaddress
import logging
import re

import voluptuous as vol
from pymodbus.client import ModbusTcpClient

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_MODBUS_ADDRESS,
    CONF_MODBUS_ADDRESS,
    CONF_READ_SCN,
    CONF_READ_SOCKET2,
    DEFAULT_READ_SCN,
    DEFAULT_READ_SOCKET2,
)
from homeassistant.core import HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_MODBUS_ADDRESS, default=DEFAULT_MODBUS_ADDRESS): int,
        vol.Optional(CONF_READ_SCN, default=DEFAULT_READ_SCN): bool,
        vol.Optional(CONF_READ_SOCKET2, default=DEFAULT_READ_SOCKET2): bool,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


def host_valid(host):
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version in (4, 6):
            return True
    except ValueError:
        disallowed = re.compile(r"[^a-zA-Z\d\-]")
        return all(x and not disallowed.search(x) for x in host.split("."))


async def async_test_connection(hass: HomeAssistant, host: str, port: int) -> bool:
    """Test if we can connect to the Modbus device."""
    try:
        client = ModbusTcpClient(host=host, port=port)
        # Run connection test in executor to avoid blocking
        result = await hass.async_add_executor_job(client.connect)
        if result:
            await hass.async_add_executor_job(client.close)
            return True
        return False
    except Exception as e:
        _LOGGER.debug("Connection test failed: %s", e)
        return False


@callback
def alfen_modbus_entries(hass: HomeAssistant):
    """Return the hosts already configured."""
    return set(
        entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
    )


class AlfenModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Alfen Modbus configflow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return AlfenModbusOptionsFlowHandler()

    def _host_in_configuration_exists(self, host) -> bool:
        """Return True if host exists in configuration."""
        if host in alfen_modbus_entries(self.hass):
            return True
        return False

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            if self._host_in_configuration_exists(host):
                errors[CONF_HOST] = "already_configured"
            elif not host_valid(user_input[CONF_HOST]):
                errors[CONF_HOST] = "invalid_host"
            elif not await async_test_connection(self.hass, host, port):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class AlfenModbusOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Alfen Modbus options."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            # Test connection if host/port changed
            current_host = self.config_entry.data.get(CONF_HOST)
            current_port = self.config_entry.data.get(CONF_PORT, DEFAULT_PORT)
            new_host = user_input.get(CONF_HOST, current_host)
            new_port = user_input.get(CONF_PORT, current_port)

            if new_host != current_host or new_port != current_port:
                if not await async_test_connection(self.hass, new_host, new_port):
                    errors["base"] = "cannot_connect"

            if not errors:
                # Merge options into data for reload
                new_data = {**self.config_entry.data, **user_input}
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                # Reload the integration to apply changes
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data=user_input)

        # Build schema with current values as defaults
        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=self.config_entry.data.get(CONF_HOST, ""),
                ): str,
                vol.Required(
                    CONF_PORT,
                    default=self.config_entry.data.get(CONF_PORT, DEFAULT_PORT),
                ): int,
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.data.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): int,
                vol.Optional(
                    CONF_READ_SCN,
                    default=self.config_entry.data.get(CONF_READ_SCN, DEFAULT_READ_SCN),
                ): bool,
                vol.Optional(
                    CONF_READ_SOCKET2,
                    default=self.config_entry.data.get(
                        CONF_READ_SOCKET2, DEFAULT_READ_SOCKET2
                    ),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )

