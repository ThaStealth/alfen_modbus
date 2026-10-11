"""The Alfen Modbus Integration."""
import asyncio
import logging
import operator
from datetime import datetime, timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from dateutil.tz import tzoffset
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    CONF_MEASUREMENT_INTERVAL,
    CONF_MODBUS_ADDRESS,
    CONF_READ_SCN,
    CONF_READ_SOCKET2,
    DEFAULT_MODBUS_ADDRESS,
    DEFAULT_NAME,
    DEFAULT_READ_SCN,
    DEFAULT_READ_SOCKET2,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_CURRENT_S,
    PHASE_SWITCH_OPTIONS,
    SCN_MAX_CURRENT_L,
    SCN_MAX_CURRENT_VALID_TIME_L,
    VALID_TIME_S,
)

# SCN_MAX_CURRENT_VALID_TIME_L keys the "SCN max current valid time" sensors below;
# unlike per-socket max current, SCN max current is not auto-renewed (see number.py).
from .repairs import async_check_firmware, async_clear_firmware_issue

_LOGGER = logging.getLogger(__name__)

ALFEN_MODBUS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.positive_int,
        vol.Optional(
            CONF_MODBUS_ADDRESS, default=DEFAULT_MODBUS_ADDRESS
        ): cv.positive_int,
        vol.Optional(CONF_READ_SCN, default=DEFAULT_READ_SCN): cv.boolean,
        vol.Optional(CONF_READ_SOCKET2, default=DEFAULT_READ_SOCKET2): cv.boolean,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(CONF_MEASUREMENT_INTERVAL): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: ALFEN_MODBUS_SCHEMA})}, extra=vol.ALLOW_EXTRA
)

PLATFORMS = ["binary_sensor", "number", "select", "sensor", "switch"]

# Registers 346-425 of a socket: apparent and reactive power, then the 16
# FLOAT64 energy totals. Starts and ends on a value boundary, because strict
# firmware rejects a read that covers part of a value.
SOCKET_TOTALS_START = 346
SOCKET_TOTALS_COUNT = 80

type AlfenConfigEntry = ConfigEntry[AlfenModbusHub]


async def async_setup(hass, config):
    """Set up the Alfen modbus component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AlfenConfigEntry):
    """Set up a alfen mobus."""
    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    port = entry.data[CONF_PORT]
    address = entry.data.get(CONF_MODBUS_ADDRESS, 1)
    scan_interval = entry.data[CONF_SCAN_INTERVAL]
    # Entries created before this option existed keep polling everything at
    # scan_interval. A measurement interval above scan_interval would make the
    # live values slower than the rest, so it is capped.
    measurement_interval = min(
        entry.data.get(CONF_MEASUREMENT_INTERVAL) or scan_interval, scan_interval
    )
    read_scn = entry.data.get(CONF_READ_SCN, False)
    read_socket2 = entry.data.get(CONF_READ_SOCKET2, False)

    _LOGGER.debug("Setup %s.%s", DOMAIN, name)

    hub = AlfenModbusHub(
        hass,
        name,
        host,
        port,
        address,
        scan_interval,
        read_scn,
        read_socket2,
        measurement_interval,
    )
    """Register the hub."""
    entry.runtime_data = hub

    # Read device info before setting up platforms so device_info is available.
    # Connecting happens lazily inside read_modbus_data (off the event loop).
    # Only treat connection-level failures as "not ready yet" (HA will retry
    # setup automatically); anything else is a real bug and should surface
    # as a normal traceback instead of retrying forever.
    try:
        await hub.read_modbus_data()
    except (ConnectionError, OSError, ModbusException) as err:
        _LOGGER.exception("Unable to connect to %s:%s", host, port)
        raise ConfigEntryNotReady(f"Unable to connect to {host}:{port}") from err

    async_check_firmware(
        hass,
        entry.entry_id,
        hub.data.get("platformType", ""),
        hub.data.get("firmwareVersion", ""),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload Alfen mobus entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        async_clear_firmware_issue(hass, entry.entry_id)
    return unload_ok


def validate(value, comparison, against):
    ops = {
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le,
        "==": operator.eq,
        "!=": operator.ne,
    }
    if not ops[comparison](value, against):
        raise ValueError(f"Value {value} failed validation ({comparison}{against})")
    return value


class AlfenModbusHub:
    """Async-safe wrapper class for pymodbus."""

    def __init__(
        self,
        hass,
        name,
        host,
        port,
        address,
        scan_interval,
        read_scn=False,
        read_socket_2=False,
        measurement_interval=None,
    ):
        """Initialize the Modbus hub."""
        self._hass = hass
        self._client = ModbusTcpClient(host=host, port=port)
        self._lock = asyncio.Lock()
        self._name = name
        self._address = address
        self.read_scn = read_scn
        self.read_socket_2 = read_socket_2
        measurement_interval = measurement_interval or scan_interval
        # refresh_max_current runs after each measurement read, so its margin is
        # based on the measurement interval.
        self._refreshInterval = measurement_interval
        self._scan_interval = timedelta(seconds=scan_interval)
        self._measurement_interval = timedelta(seconds=measurement_interval)
        self._unsub_interval_method = None
        self._unsub_measurement_method = None
        self._measurement_busy = False
        self._slow_busy = False
        # Identification is static, so it is read at setup only, and again when
        # the charger restarts (for example after a firmware update).
        self._last_uptime_ms = None
        self._identification_pending = False
        self._sensors = []
        self._inputs = []
        self.data = {}
        self._closing = False

    @callback
    def async_add_alfen_sensor(self, update_callback, refresh_callback = None):
        """Listen for data updates."""
        # This is the first sensor, set up the intervals.
        if not self._sensors:
            self._closing = False
            self._unsub_interval_method = async_track_time_interval(
                self._hass, self.async_refresh_slow_data, self._scan_interval
            )
            self._unsub_measurement_method = async_track_time_interval(
                self._hass, self.async_refresh_modbus_data, self._measurement_interval
            )
            # Schedule initial data read as a task (non-blocking); pymodbus's
            # sync client connects on demand from within that executor job.
            self._hass.async_create_task(self.read_modbus_data())

        self._sensors.append(update_callback)
        if refresh_callback is not None:
           self._inputs.append(refresh_callback)

    @callback
    def async_remove_alfen_sensor(self, update_callback, refresh_callback = None):
        """Remove data update."""
        self._sensors.remove(update_callback)
        if refresh_callback is not None:
           self._inputs.remove(refresh_callback)
        if not self._sensors:
            """stop the interval timers upon removal of last sensor"""
            self._unsub_interval_method()
            self._unsub_interval_method = None
            self._unsub_measurement_method()
            self._unsub_measurement_method = None
            # Block any read still in flight from silently reopening the
            # connection after we close it below (pymodbus auto-connects).
            self._closing = True
            # Close under the lock, off the event loop, so this can't race
            # an in-flight executor read/write on the same socket.
            self._hass.async_create_task(self._async_close())

    async def _async_close(self):
        async with self._lock:
            try:
                await self._hass.async_add_executor_job(self._client.close)
            except Exception as err:  # noqa: BLE001 - teardown must never raise
                _LOGGER.debug("Error closing Modbus client: %s", err)

    def _notify_sensors(self) -> None:
        for update_callback in self._sensors:
            update_callback()

    async def async_refresh_modbus_data(self, _now: datetime | None = None) -> None:
        """Read the live measurements.

        Called by the measurement timer, and by the number, select and switch
        entities right after a write, so a new setpoint shows up without
        waiting a cycle.
        """
        if not self._sensors:
            return
        # A timer tick while the previous read still runs is dropped, so reads
        # never pile up at short intervals. A refresh after a write always runs.
        if _now is not None and self._measurement_busy:
            return

        self._measurement_busy = True
        try:
            update_result = await self.read_modbus_data_measurements()
        except Exception:
            _LOGGER.exception("Error reading modbus measurement data")
            update_result = False
        finally:
            self._measurement_busy = False

        if update_result:
            self._notify_sensors()
            self.refresh_max_current()

    async def async_refresh_slow_data(self, _now: datetime | None = None) -> None:
        """Read the registers that change slowly (energy totals, station data)."""
        if not self._sensors or self._slow_busy:
            return

        self._slow_busy = True
        try:
            update_result = await self.read_modbus_data_slow()
        except Exception:
            _LOGGER.exception("Error reading modbus data")
            update_result = False
        finally:
            self._slow_busy = False

        if update_result:
            self._notify_sensors()

    @property
    def name(self):
        """Return the name of this hub."""
        return self._name

    @property
    def has_socket_2(self):
        """Return true if a meter is available"""
        return self.read_socket_2

    @property
    def has_scn(self):
        """Return true if a battery is available"""
        return self.read_scn

    async def read_holding_registers(self, unit, address, count):
        """Read holding registers."""
        def _do_read():
            # Runs in the executor thread, off the event loop: pymodbus's
            # sync client connects on demand inside read_holding_registers.
            return self._client.read_holding_registers(address=address, count=count, device_id=unit)

        try:
            async with self._lock:
                if self._closing:
                    # Lost the race with teardown: the socket may already be
                    # closed. Don't let pymodbus silently reopen it here, and
                    # don't go through the reconnect-retry path below for it.
                    return None
                return await self._hass.async_add_executor_job(_do_read)
        except (BrokenPipeError, ConnectionError, OSError, ModbusException) as e:
            if self._closing:
                return None
            _LOGGER.warning("Connection error during read, attempting reconnect: %s", e)
            # Try to reconnect once
            def _do_reconnect_and_read():
                try:
                    self._client.close()
                except (OSError, ModbusException) as close_err:
                    _LOGGER.debug("Error closing Modbus client before reconnect: %s", close_err)
                self._client.connect()
                return self._client.read_holding_registers(address=address, count=count, device_id=unit)

            try:
                async with self._lock:
                    return await self._hass.async_add_executor_job(_do_reconnect_and_read)
            except Exception as retry_error:
                _LOGGER.error("Failed to reconnect and retry read: %s", retry_error)
                raise

    async def write_registers(self, unit, address, payload):
        """Write registers."""
        def _do_write():
            # Runs in the executor thread, off the event loop: pymodbus's
            # sync client connects on demand inside write_registers.
            return self._client.write_registers(address=address, values=payload, device_id=unit)

        try:
            async with self._lock:
                if self._closing:
                    return None
                return await self._hass.async_add_executor_job(_do_write)
        except (BrokenPipeError, ConnectionError, OSError, ModbusException) as e:
            if self._closing:
                return None
            _LOGGER.warning("Connection error during write, attempting reconnect: %s", e)
            # Try to reconnect once
            def _do_reconnect_and_write():
                try:
                    self._client.close()
                except (OSError, ModbusException) as close_err:
                    _LOGGER.debug("Error closing Modbus client before reconnect: %s", close_err)
                self._client.connect()
                return self._client.write_registers(address=address, values=payload, device_id=unit)

            try:
                async with self._lock:
                    return await self._hass.async_add_executor_job(_do_reconnect_and_write)
            except Exception as retry_error:
                _LOGGER.error("Failed to reconnect and retry write: %s", retry_error)
                raise

    def refresh_max_current(self):
        # Guard against KeyError if data hasn't been populated yet
        key1 = VALID_TIME_S + "1"
        key2 = VALID_TIME_S + "2"
        if key1 not in self.data:
            return
        if int(self.data[key1]) < self._refreshInterval+10 or (self.has_socket_2 and key2 in self.data and int(self.data[key2]) < self._refreshInterval+10):
            for update_callback in self._inputs:
                # Schedule async callbacks as tasks
                result = update_callback()
                if asyncio.iscoroutine(result):
                    self._hass.async_create_task(result)

    async def read_modbus_data(self):
        """Read every register group once (setup and first update).

        The slow group comes before the measurements: the session start that
        the measurement read detects needs the energy total and station time.
        """
        if self._closing:
            return False
        return (
            await self.read_modbus_data_product()
            and await self.read_modbus_data_slow()
            and await self.read_modbus_data_measurements()
        )

    async def read_modbus_data_slow(self):
        """Station time and status, SCN, and the per-socket totals."""
        if not await self.read_modbus_data_station_time():
            return False
        # A failed read (the charger may still be booting) is retried next cycle;
        # it does not block the rest of the slow read.
        if self._identification_pending and await self.read_modbus_data_product():
            self._identification_pending = False
        return (
            await self.read_modbus_data_station()
            and await self.read_modbus_data_scn()
            and await self.read_modbus_data_socket_totals(1)
            and await self.read_modbus_data_socket_totals(2)
        )

    async def read_modbus_data_measurements(self):
        """Live meter values and socket status: the load balancing inputs."""
        return (
            await self.read_modbus_data_socket(1)
            and await self.read_modbus_data_socket(2)
        )

    def _socket_enabled(self, socket):
        return socket == 1 or (
            socket == 2 and self.has_socket_2 and self.data.get("numberOfSockets", 0) >= 2
        )

    def decode_string(self, decoder,length):
        s = decoder.decode_string(length*2)  # get 32 char string
        s = s.partition(b"\0")[0]  # omit NULL terminators
        s = s.decode("utf-8")  # decode UTF-8
        return str(s)

    def decode_from_registers(self, registers, offset, count, data_type):
        return self._client.convert_from_registers(registers[offset:offset+count], data_type=data_type, word_order='big')

    async def read_modbus_data_station(self):
        status_data = await self.read_holding_registers(self._address,1100,6)
        if status_data is None or status_data.isError():
            return False

        self.data["actualMaxCurrent"] =  round(self.decode_from_registers(status_data.registers,0,2,self._client.DATATYPE.FLOAT32),2)
        self.data["boardTemperature"] =  round(self.decode_from_registers(status_data.registers,2,2,self._client.DATATYPE.FLOAT32),3)
        self.data["backofficeConnected"] = self.data["backoffice"] = self.decode_from_registers(status_data.registers,4,1,self._client.DATATYPE.UINT16)
        self.data["numberOfSockets"] = self.decode_from_registers(status_data.registers,5,1,self._client.DATATYPE.UINT16)
        return True

    async def read_modbus_data_scn(self):
        if(self.has_scn):
            status_data = await self.read_holding_registers(self._address,1400,32)
            if status_data is None or status_data.isError():
                return False

            self.data["scnName"] = self.decode_from_registers(status_data.registers,0,4,self._client.DATATYPE.STRING).strip('\x00')
            self.data["scnSockets"] =  self.decode_from_registers(status_data.registers,4,1,self._client.DATATYPE.UINT16)

            self.data["scnTotalConsumptionL1"] = round(self.decode_from_registers(status_data.registers,5,2,self._client.DATATYPE.FLOAT32),2)
            self.data["scnTotalConsumptionL2"] = round(self.decode_from_registers(status_data.registers,7,2,self._client.DATATYPE.FLOAT32),2)
            self.data["scnTotalConsumptionL3"] = round(self.decode_from_registers(status_data.registers,9,2,self._client.DATATYPE.FLOAT32),2)

            self.data["scnActualMaxCurrentL1"] = round(self.decode_from_registers(status_data.registers,11,2,self._client.DATATYPE.FLOAT32),2)
            self.data["scnActualMaxCurrentL2"] = round(self.decode_from_registers(status_data.registers,13,2,self._client.DATATYPE.FLOAT32),2)
            self.data["scnActualMaxCurrentL3"] = round(self.decode_from_registers(status_data.registers,15,2,self._client.DATATYPE.FLOAT32),2)

            self.data[SCN_MAX_CURRENT_L+"L1"] = round(self.decode_from_registers(status_data.registers,17,2,self._client.DATATYPE.FLOAT32),2)
            self.data[SCN_MAX_CURRENT_L+"L2"] = round(self.decode_from_registers(status_data.registers,19,2,self._client.DATATYPE.FLOAT32),2)
            self.data[SCN_MAX_CURRENT_L+"L3"] = round(self.decode_from_registers(status_data.registers,21,2,self._client.DATATYPE.FLOAT32),2)

            self.data[SCN_MAX_CURRENT_VALID_TIME_L+"L1"] = self.decode_from_registers(status_data.registers,23,2,self._client.DATATYPE.UINT32)
            self.data[SCN_MAX_CURRENT_VALID_TIME_L+"L2"] = self.decode_from_registers(status_data.registers,25,2,self._client.DATATYPE.UINT32)
            self.data[SCN_MAX_CURRENT_VALID_TIME_L+"L3"] = self.decode_from_registers(status_data.registers,27,2,self._client.DATATYPE.UINT32)

            self.data["scnSafeCurrent"] = round(self.decode_from_registers(status_data.registers,29,2,self._client.DATATYPE.FLOAT32),2)
            self.data["scnMaxCurrentEnabled"] = self.decode_from_registers(status_data.registers,31,1,self._client.DATATYPE.UINT16)
        return True

    async def read_modbus_data_socket(self,socket):
        """Live measurements and status of one socket.

        Registers 300-345 (meter state and age, voltages, currents, power) and
        1200-1215 (mode 3 state, setpoint). The totals in 346-425 are read by
        read_modbus_data_socket_totals at the slower scan interval.
        """
        if not self._socket_enabled(socket):
            return True

        energy_data = await self.read_holding_registers(socket,300,46)
        if energy_data is None or energy_data.isError():
            return False

        self.data["socket_"+str(socket)+"_meterstate"] =  self.decode_from_registers(energy_data.registers,0,1,self._client.DATATYPE.UINT16)
        # Register is UNSIGNED64 in units of 0.001s (milliseconds); convert to
        # seconds to match the sensor's "s" unit. A reserved/unavailable register
        # reads back as all-1s (NaN per the spec) - surface that as unknown rather
        # than a bogus multi-million-year age.
        raw_meter_age = self.decode_from_registers(energy_data.registers,1,4,self._client.DATATYPE.UINT64)
        self.data["socket_"+str(socket)+"_meterAge"] = None if raw_meter_age == 0xFFFFFFFFFFFFFFFF else round(raw_meter_age / 1000, 3)
        self.data["socket_"+str(socket)+"_meterType"] =  self.decode_from_registers(energy_data.registers,5,1,self._client.DATATYPE.UINT16)

        self.data["socket_"+str(socket)+"_VL1-N"] =   round(self.decode_from_registers(energy_data.registers,6,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_VL2-N"] =   round(self.decode_from_registers(energy_data.registers,8,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_VL3-N"] =   round(self.decode_from_registers(energy_data.registers,10,2,self._client.DATATYPE.FLOAT32),2)

        self.data["socket_"+str(socket)+"_VL1-L2"] =  round(self.decode_from_registers(energy_data.registers,12,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_VL2-L3"] =   round(self.decode_from_registers(energy_data.registers,14,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_VL3-L1"] =   round(self.decode_from_registers(energy_data.registers,16,2,self._client.DATATYPE.FLOAT32),2)

        self.data["socket_"+str(socket)+"_currentN"] =   round(self.decode_from_registers(energy_data.registers,18,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_currentL1"] =   round(self.decode_from_registers(energy_data.registers,20,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_currentL2"] =   round(self.decode_from_registers(energy_data.registers,22,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_currentL3"] =  round(self.decode_from_registers(energy_data.registers,24,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_currentSum"] =   round(self.decode_from_registers(energy_data.registers,26,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_powerL1"] =  round(self.decode_from_registers(energy_data.registers,28,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_powerL2"] =   round(self.decode_from_registers(energy_data.registers,30,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_powerL3"] =  round(self.decode_from_registers(energy_data.registers,32,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_powerSum"] =   round(self.decode_from_registers(energy_data.registers,34,2,self._client.DATATYPE.FLOAT32),2)

        self.data["socket_"+str(socket)+"_frequency"] =   round(self.decode_from_registers(energy_data.registers,36,2,self._client.DATATYPE.FLOAT32),3)

        self.data["socket_"+str(socket)+"_realPowerL1"] =   round(self.decode_from_registers(energy_data.registers,38,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_realPowerL2"] =   round(self.decode_from_registers(energy_data.registers,40,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_realPowerL3"] =   round(self.decode_from_registers(energy_data.registers,42,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_realPowerSum"] =   round(self.decode_from_registers(energy_data.registers,44,2,self._client.DATATYPE.FLOAT32),2)

        status_data = await self.read_holding_registers(socket,1200,16)
        if status_data is None or status_data.isError():
            return False

        self.data["socket_"+str(socket)+"_available"] =  self.decode_from_registers(status_data.registers, 0, 1,self._client.DATATYPE.UINT16)
        mode3 = self.decode_from_registers(status_data.registers, 1, 5, self._client.DATATYPE.STRING).strip('\x00').strip().upper()
        self.data["socket_"+str(socket)+"_mode3state"] = mode3
        self.data["socket_"+str(socket)+"_actualMaxCurrent"] =   round(self.decode_from_registers(status_data.registers,6,2,self._client.DATATYPE.FLOAT32),2)
        self.data[VALID_TIME_S+str(socket)] = self.decode_from_registers(status_data.registers, 8, 2,self._client.DATATYPE.UINT32)
        self.data[MAX_CURRENT_S+str(socket)] =  round(self.decode_from_registers(status_data.registers,10,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_saveCurrent"] =  round(self.decode_from_registers(status_data.registers,12,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_setpointAccounted"] =  self.decode_from_registers(status_data.registers, 14, 1,self._client.DATATYPE.UINT16)
        self.data["socket_"+str(socket)+"_chargephases"] =  self.decode_from_registers(status_data.registers, 15, 1,self._client.DATATYPE.UINT16)

        # IEC 61851 state families: A/E/F idle, B/C1/D1 connected but not
        # drawing current, C2/D2 charging (PWM applied - see the Mode 3
        # State table: only C2 and D2 have "Charging: Yes"). Endswith("2")
        # rather than an exact-match set, to tolerate trailing junk some
        # firmware versions have been observed to append to the string.
        if not mode3 or mode3.startswith(("A", "E", "F")):
            self.data["socket_"+str(socket)+"_carconnected"] = 0
        else:
            self.data["socket_"+str(socket)+"_carconnected"] = 1

        if mode3.startswith(("C", "D")) and mode3.endswith("2"):
            self.data["socket_"+str(socket)+"_carcharging"] = 1
        else:
            self.data["socket_"+str(socket)+"_carcharging"] = 0

        # Alfen has no dedicated enable/disable coil, so "enabled" is
        # derived from the max-current setpoint itself (register 1210):
        # 0 A means charging is disabled, matching the charger_enabled
        # switch's on/off semantics below.
        self.data["socket_"+str(socket)+"_chargerenabled"] = 1 if self.data[MAX_CURRENT_S+str(socket)] > 0 else 0

        # Session tracks the whole connected period (plug-in to unplug), not
        # just PWM-active spans, so a brief charging pause (e.g. C2->C1->C2)
        # doesn't reset the session's accumulated Wh/duration. Only state A
        # (no vehicle) ends it. E and F are error and not-available states with
        # the car possibly still plugged in: Alfen reports E for a few seconds
        # at the end of a charge. They neither end nor start a session.
        if not mode3 or mode3.startswith("A"):
            self.data.pop("socket_"+str(socket)+"_chargingStartWh", None)
            self.data.pop("socket_"+str(socket)+"_chargingStart", None)
        elif mode3.startswith(("B", "C", "D")) and "socket_"+str(socket)+"_chargingStartWh" not in self.data:
            # The totals come from the last slow read. No energy is delivered
            # before the car is connected, so that total is the start value;
            # the start time can be up to one scan interval early.
            start_wh = self.data.get("socket_"+str(socket)+"_realEnergyDeliveredSum")
            start = self.data.get("stationTime")
            if start_wh is not None and start is not None:
                self.data["socket_"+str(socket)+"_chargingStartWh"] = start_wh
                self.data["socket_"+str(socket)+"_chargingStart"] = start

        self._update_session(socket)

        if self.data["socket_"+str(socket)+"_chargephases"] in PHASE_SWITCH_OPTIONS:
            self.data["usephases_S"+str(socket)] = PHASE_SWITCH_OPTIONS[self.data["socket_"+str(socket)+"_chargephases"]]
        return True

    async def read_modbus_data_socket_totals(self,socket):
        """Apparent and reactive power, and the energy totals (registers 346-425)."""
        if not self._socket_enabled(socket):
            return True

        totals_data = await self.read_holding_registers(socket,SOCKET_TOTALS_START,SOCKET_TOTALS_COUNT)
        if totals_data is None or totals_data.isError():
            return False

        # Pad to keep the offsets relative to register 300, as in the register map.
        registers = [0] * (SOCKET_TOTALS_START - 300) + list(totals_data.registers)

        self.data["socket_"+str(socket)+"_apparantPowerL1"] =   round(self.decode_from_registers(registers,46,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_apparantPowerL2"] =   round(self.decode_from_registers(registers,48,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_apparantPowerL3"] =  round(self.decode_from_registers(registers,50,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_apparantPowerSum"] =  round(self.decode_from_registers(registers,52,2,self._client.DATATYPE.FLOAT32),2)

        self.data["socket_"+str(socket)+"_reactivePowerL1"] =   round(self.decode_from_registers(registers,54,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_reactivePowerL2"] =   round(self.decode_from_registers(registers,56,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_reactivePowerL3"] =   round(self.decode_from_registers(registers,58,2,self._client.DATATYPE.FLOAT32),2)
        self.data["socket_"+str(socket)+"_reactivePowerSum"] =   round(self.decode_from_registers(registers,60,2,self._client.DATATYPE.FLOAT32),2)

        self.data["socket_"+str(socket)+"_realEnergyDeliveredL1"] = round(self.decode_from_registers(registers,62,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_realEnergyDeliveredL2"] =   round(self.decode_from_registers(registers,66,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_realEnergyDeliveredL3"] =   round(self.decode_from_registers(registers,70,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_realEnergyDeliveredSum"] =   round(self.decode_from_registers(registers,74,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_realEnergyConsumedL1"] =  round(self.decode_from_registers(registers,78,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_realEnergyConsumedL2"] =   round(self.decode_from_registers(registers,82,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_realEnergyConsumedL3"] =  round(self.decode_from_registers(registers,86,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_realEnergyConsumedSum"] =   round(self.decode_from_registers(registers,90,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_apparantEnergyL1"] =  round(self.decode_from_registers(registers,94,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_apparantEnergyL2"] =  round(self.decode_from_registers(registers,98,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_apparantEnergyL3"] =  round(self.decode_from_registers(registers,102,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_apparantEnergySum"] =  round(self.decode_from_registers(registers,106,4,self._client.DATATYPE.FLOAT64),2)

        self.data["socket_"+str(socket)+"_reactiveEnergyL1"] =  round(self.decode_from_registers(registers,110,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_reactiveEnergyL2"] =  round(self.decode_from_registers(registers,114,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_reactiveEnergyL3"] =  round(self.decode_from_registers(registers,118,4,self._client.DATATYPE.FLOAT64),2)
        self.data["socket_"+str(socket)+"_reactiveEnergySum"] = round(self.decode_from_registers(registers,122,4,self._client.DATATYPE.FLOAT64),2)

        self._update_session(socket)
        return True

    def _update_session(self, socket):
        """Energy and duration of the session in progress, if any."""
        s = "socket_"+str(socket)+"_"
        start_wh = self.data.get(s+"chargingStartWh")
        start = self.data.get(s+"chargingStart")
        if start_wh is None or start is None:
            return
        if s+"realEnergyDeliveredSum" in self.data and "stationTime" in self.data:
            self.data[s+"currentSession"] = self.data[s+"realEnergyDeliveredSum"] - start_wh
            self.data[s+"currentSessionDuration"] = int((self.data["stationTime"] - start).total_seconds())

    async def read_modbus_data_product(self):
        """Product identification (registers 100-167). Static: read at setup."""
        identification_data = await self.read_holding_registers(self._address, 100, 68)
        if identification_data is None or identification_data.isError():
            return False

        self.data["name"] = self.decode_from_registers(identification_data.registers, 0, 17, self._client.DATATYPE.STRING).strip('\x00')
        self.data["manufacturer"] = self.decode_from_registers(identification_data.registers, 17, 5, self._client.DATATYPE.STRING).strip('\x00')
        self.data["modbustableVersion"] = self.decode_from_registers(identification_data.registers, 22, 1,self._client.DATATYPE.INT16)
        self.data["firmwareVersion"] = self.decode_from_registers(identification_data.registers, 23, 17, self._client.DATATYPE.STRING).strip('\x00')
        self.data["platformType"] = self.decode_from_registers(identification_data.registers, 40, 17, self._client.DATATYPE.STRING).strip('\x00')
        self.data["serial"] = self.decode_from_registers(identification_data.registers, 57, 11, self._client.DATATYPE.STRING).strip('\x00')
        return True

    async def read_modbus_data_station_time(self):
        """Station clock and uptime (registers 168-178)."""
        time_data = await self.read_holding_registers(self._address, 168, 11)
        if time_data is None or time_data.isError():
            return False

        year    = self.decode_from_registers(time_data.registers, 0, 1,self._client.DATATYPE.INT16)
        month   = self.decode_from_registers(time_data.registers, 1, 1,self._client.DATATYPE.INT16)
        day     = self.decode_from_registers(time_data.registers, 2, 1,self._client.DATATYPE.INT16)
        hour    = self.decode_from_registers(time_data.registers, 3, 1,self._client.DATATYPE.INT16)
        minute  = self.decode_from_registers(time_data.registers, 4, 1,self._client.DATATYPE.INT16)
        second  = self.decode_from_registers(time_data.registers, 5, 1,self._client.DATATYPE.INT16)
        uptime  = self.decode_from_registers(time_data.registers, 6, 4,self._client.DATATYPE.UINT64)
        utcoffset = self.decode_from_registers(time_data.registers, 10, 1,self._client.DATATYPE.INT16)

        # Uptime only goes back on a restart. Unlike lastBoot it does not move
        # when the station clock is corrected.
        if self._last_uptime_ms is not None and uptime < self._last_uptime_ms:
            _LOGGER.info("Charger restarted, reading its identification again")
            self._identification_pending = True
        self._last_uptime_ms = uptime

        # Tijdconversie
        self.data["stationTime"] = datetime(
            year, month, day, hour, minute, second,
            tzinfo=tzoffset("", utcoffset * 60)
        )

        last_boot = self.data["stationTime"] - timedelta(milliseconds=uptime)
        self.data["lastBoot"] = last_boot.replace(microsecond=0)

        return True
