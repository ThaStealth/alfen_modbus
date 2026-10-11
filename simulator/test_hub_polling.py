"""
Tests the real AlfenModbusHub (custom_components/alfen_modbus) against the
simulator, with the few Home Assistant imports stubbed out.

Covers:
  - every socket value decodes from the register given in the Alfen register
    map (the test holds its own copy of the addresses)
  - which registers each kind of read requests
  - timer rates, the write-triggered refresh, the busy guard and the
    max current refresh
  - Mode 3 state families, the session across a charging pause, the
    charger-enabled flag and the meter age "not available" value
  - the outdated NG9xx firmware repair issue, and no reads after teardown
  - identification: read at setup and reload, and again after a charger
    restart (with a retry when that read fails)
  - how async_setup_entry picks the measurement interval, and the config schema

Usage:
    python test_hub_polling.py            # starts its own simulators on 5021/5022

    ALFEN_SIM_PYTHON=<python> python test_hub_polling.py
        runs the simulators with another interpreter, for example to test the
        hub with a pymodbus version that the simulator does not support

Requires pymodbus >= 3.11.2, voluptuous and python-dateutil.
"""
import asyncio
import datetime as dt
import importlib
import itertools
import logging
import os
import struct
import subprocess
import sys
import time
import types
from concurrent.futures import ThreadPoolExecutor

import voluptuous as vol
from pymodbus.client import AsyncModbusTcpClient

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATIC_PORT = 5021
LIVE_PORT = 5022

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("hub_test")
log.setLevel(logging.INFO)

# Repair issues raised through the stubbed issue registry, by issue id.
ISSUES = {}

# Socket values in the Alfen Modbus register map, in register order: the
# FLOAT32 values fill 306-361 and the FLOAT64 energy totals fill 362-425.
FLOAT32_KEYS = [
    "VL1-N", "VL2-N", "VL3-N", "VL1-L2", "VL2-L3", "VL3-L1",
    "currentN", "currentL1", "currentL2", "currentL3", "currentSum",
    "powerL1", "powerL2", "powerL3", "powerSum", "frequency",
    "realPowerL1", "realPowerL2", "realPowerL3", "realPowerSum",
    "apparantPowerL1", "apparantPowerL2", "apparantPowerL3", "apparantPowerSum",
    "reactivePowerL1", "reactivePowerL2", "reactivePowerL3", "reactivePowerSum",
]
FLOAT64_KEYS = [
    f"{kind}{phase}"
    for kind in ("realEnergyDelivered", "realEnergyConsumed", "apparantEnergy", "reactiveEnergy")
    for phase in ("L1", "L2", "L3", "Sum")
]
REGISTER_MAP = (
    [(key, 306 + 2 * i, 2) for i, key in enumerate(FLOAT32_KEYS)]
    + [(key, 362 + 4 * i, 4) for i, key in enumerate(FLOAT64_KEYS)]
)


# ============================================================================
# Home Assistant stubs
# ============================================================================

def install_ha_stubs():
    """Register the minimal homeassistant modules the integration imports."""
    ha = types.ModuleType("homeassistant")
    ha.__path__ = []

    const = types.ModuleType("homeassistant.const")
    const.CONF_NAME, const.CONF_HOST = "name", "host"
    const.CONF_PORT, const.CONF_SCAN_INTERVAL = "port", "scan_interval"

    core = types.ModuleType("homeassistant.core")
    core.callback = lambda func: func
    core.HomeAssistant = type("HomeAssistant", (), {})

    exceptions = types.ModuleType("homeassistant.exceptions")
    exceptions.ConfigEntryNotReady = type("ConfigEntryNotReady", (Exception,), {})

    entries = types.ModuleType("homeassistant.config_entries")
    entries.ConfigEntry = type("ConfigEntry", (), {})

    class ConfigFlow:
        def __init_subclass__(cls, domain=None, **kwargs):
            super().__init_subclass__(**kwargs)

    entries.ConfigFlow = ConfigFlow
    entries.OptionsFlow = type("OptionsFlow", (), {})
    entries.CONN_CLASS_LOCAL_POLL = "local_poll"
    ha.config_entries = entries

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    cv = types.ModuleType("homeassistant.helpers.config_validation")
    cv.string, cv.boolean, cv.slug = str, bool, str
    cv.positive_int = vol.All(vol.Coerce(int), vol.Range(min=0))

    event = types.ModuleType("homeassistant.helpers.event")

    def async_track_time_interval(hass, action, interval):
        # Like HA: each tick runs as its own task, so a slow read can overlap the
        # next tick. That is what the busy guard in the hub is for.
        async def ticker():
            while True:
                await asyncio.sleep(interval.total_seconds())
                asyncio.get_running_loop().create_task(action(dt.datetime.now(dt.UTC)))

        task = asyncio.get_running_loop().create_task(ticker())
        return task.cancel

    event.async_track_time_interval = async_track_time_interval

    issues = types.ModuleType("homeassistant.helpers.issue_registry")
    issues.IssueSeverity = types.SimpleNamespace(WARNING="warning")
    issues.async_create_issue = lambda hass, domain, issue_id, **kwargs: ISSUES.__setitem__(issue_id, kwargs)
    issues.async_delete_issue = lambda hass, domain, issue_id: ISSUES.pop(issue_id, None)
    helpers.issue_registry = issues

    sys.modules.update({
        "homeassistant": ha,
        "homeassistant.const": const,
        "homeassistant.core": core,
        "homeassistant.exceptions": exceptions,
        "homeassistant.config_entries": entries,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.config_validation": cv,
        "homeassistant.helpers.event": event,
        "homeassistant.helpers.issue_registry": issues,
    })


class FakeHass:
    """Just enough of hass for the hub: executor jobs, tasks, entry setup."""

    def __init__(self):
        self.data = {}
        self._executor = ThreadPoolExecutor(4)
        self.config_entries = types.SimpleNamespace(
            async_forward_entry_setups=self._forward,
            async_forward_entry_unload=self._unload,
        )

    async def _forward(self, entry, platforms):
        return True

    async def _unload(self, entry, platform):
        return True

    def async_add_executor_job(self, func, *args):
        return asyncio.get_running_loop().run_in_executor(self._executor, func, *args)

    def async_create_task(self, coro):
        return asyncio.get_running_loop().create_task(coro)


# ============================================================================
# Helpers
# ============================================================================

class Results:
    def __init__(self):
        self.passed = 0
        self.failed = []

    def check(self, name, condition, detail=""):
        if condition:
            self.passed += 1
            log.info(f"  PASS  {name}")
        else:
            self.failed.append(name)
            log.error(f"  FAIL  {name} {detail}")


def record_reads(hub):
    """Wrap hub.read_holding_registers to log (unit, address, count) per call."""
    calls = []
    original = hub.read_holding_registers

    async def wrapper(unit, address, count):
        calls.append((unit, address, count))
        return await original(unit, address, count)

    hub.read_holding_registers = wrapper
    return calls


_entry_ids = itertools.count(1)


def make_entry(**data):
    """A config entry as async_setup_entry sees it."""
    return types.SimpleNamespace(entry_id=f"entry{next(_entry_ids)}", data=data, runtime_data=None)


def float_registers(value):
    raw = struct.pack(">f", float(value))
    return [int.from_bytes(raw[0:2], "big"), int.from_bytes(raw[2:4], "big")]


def string_registers(text, length_bytes):
    raw = text.encode("utf-8")[:length_bytes].ljust(length_bytes, b"\x00")
    return [int.from_bytes(raw[i:i + 2], "big") for i in range(0, length_bytes, 2)]


def uint64_registers(value):
    raw = struct.pack(">Q", int(value))
    return [int.from_bytes(raw[i:i + 2], "big") for i in range(0, 8, 2)]


def decode_registers(registers):
    raw = b"".join(int(r).to_bytes(2, "big") for r in registers)
    return struct.unpack(">f" if len(raw) == 4 else ">d", raw)[0]


def start_simulator(port, static):
    # ALFEN_SIM_PYTHON runs the simulator under another interpreter, so the hub
    # can be tested with a pymodbus version the simulator does not support.
    python = os.environ.get("ALFEN_SIM_PYTHON", sys.executable)
    args = [python, os.path.join(HERE, "simulator.py"), "-p", str(port)]
    if static:
        args.append("--static")
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc


async def wait_for_port(port, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        client = AsyncModbusTcpClient("127.0.0.1", port=port)
        await client.connect()
        if client.connected:
            client.close()
            return True
        await asyncio.sleep(0.5)
    return False


async def sim_write(port, unit, address, registers):
    client = AsyncModbusTcpClient("127.0.0.1", port=port)
    await client.connect()
    await client.write_registers(address, registers, device_id=unit)
    client.close()


async def sim_read(port, unit, address, count):
    client = AsyncModbusTcpClient("127.0.0.1", port=port)
    await client.connect()
    result = await client.read_holding_registers(address, count=count, device_id=unit)
    client.close()
    return result.registers


# ============================================================================
# Tests
# ============================================================================

async def test_register_map(new_mod, hass, results):
    log.info("\n=== Decodes against the register map (static simulator) ===")
    hub = new_mod.AlfenModbusHub(hass, "alfen", "127.0.0.1", STATIC_PORT, 200, 30)
    await hub.read_modbus_data()
    hub._client.close()

    wrong = []
    for key, address, count in REGISTER_MAP:
        expected = decode_registers(await sim_read(STATIC_PORT, 1, address, count))
        got = hub.data.get(f"socket_1_{key}")
        if got is None or abs(got - expected) > 0.006:
            wrong.append(f"{key}@{address}: hub {got!r}, register {expected!r}")
    results.check(f"all {len(REGISTER_MAP)} socket values decode from their register", not wrong, "; ".join(wrong))
    results.check("apparent energy L1 comes from 394, after real energy consumed sum (390-393)",
                  hub.data.get("socket_1_apparantEnergyL1") == 15542.0, f"got {hub.data.get('socket_1_apparantEnergyL1')!r}")
    results.check("reactive energy sum comes from 422-425",
                  hub.data.get("socket_1_reactiveEnergySum") == 9169.0, f"got {hub.data.get('socket_1_reactiveEnergySum')!r}")
    results.check("meter age is one value in seconds (500 ms -> 0.5)", hub.data.get("socket_1_meterAge") == 0.5)
    duration = hub.data.get("socket_1_currentSessionDuration")
    results.check("session duration is whole seconds, not a timedelta", isinstance(duration, int), f"got {duration!r}")
    results.check("usable phases use the select's literal option", hub.data.get("usephases_S1") == "3",
                  f"got {hub.data.get('usephases_S1')!r}")


async def test_request_plan(new_mod, hass, results):
    log.info("\n=== Registers requested per read ===")
    hub = new_mod.AlfenModbusHub(hass, "alfen", "127.0.0.1", STATIC_PORT, 200, 30, measurement_interval=2)
    calls = record_reads(hub)

    await hub.read_modbus_data()
    full = list(calls)
    calls.clear()
    await hub.read_modbus_data_measurements()
    measurement = list(calls)
    calls.clear()
    await hub.read_modbus_data_slow()
    slow = list(calls)
    hub._client.close()

    results.check("full read: identification once, then slow, then measurements",
                  full == [(200, 100, 68), (200, 168, 11), (200, 1100, 6), (1, 346, 80), (1, 300, 46), (1, 1200, 16)],
                  f"got {full}")
    results.check("measurement read: 300-345 and 1200-1215 only", measurement == [(1, 300, 46), (1, 1200, 16)], f"got {measurement}")
    results.check("slow read: clock, station, totals 346-425 (no identification)",
                  slow == [(200, 168, 11), (200, 1100, 6), (1, 346, 80)], f"got {slow}")
    results.check("no request above the 125-register limit", all(c <= 125 for _, _, c in full + slow))
    log.info(f"        measurement read: {sum(c for _, _, c in measurement)} registers in {len(measurement)} requests")


async def test_timers_and_writes(new_mod, hass, results):
    log.info("\n=== Timers, write refresh, busy guard (live simulator) ===")
    hub = new_mod.AlfenModbusHub(hass, "alfen", "127.0.0.1", LIVE_PORT, 200, 4, measurement_interval=1)
    calls = record_reads(hub)
    notified = []
    max_current_refreshes = []
    hub.async_add_alfen_sensor(lambda: notified.append(time.time()), lambda: max_current_refreshes.append(time.time()))

    ages = []
    start = time.time()
    while time.time() - start < 12:
        await asyncio.sleep(0.25)
        if hub.data.get("socket_1_meterAge") is not None:
            ages.append(hub.data["socket_1_meterAge"])
    count = lambda address: sum(1 for _, a, _ in calls if a == address)
    log.info(f"        12 s: measurement reads {count(300)}, slow reads {count(346)}, identification reads {count(100)}")
    results.check("measurement timer ~1 s (10-14 reads in 12 s)", 10 <= count(300) <= 14, f"got {count(300)}")
    results.check("scan timer ~4 s (3-5 reads in 12 s, incl. the first full read)", 3 <= count(346) <= 5, f"got {count(346)}")
    results.check("identification read once", count(100) == 1, f"got {count(100)}")
    results.check("meter age always under 1 s and changing", ages and max(ages) < 1 and len(set(ages)) > 3,
                  f"values {sorted(set(ages))[:6]}")

    # A write is followed by a measurement-only refresh. Stop the scan timer
    # first: its own reads would otherwise land in this check at random.
    hub._unsub_interval_method()
    hub._unsub_interval_method = lambda: None
    await asyncio.sleep(0.5)
    calls.clear()
    payload = float_registers(10.0)
    await hub.write_registers(unit=1, address=1210, payload=payload)
    await hub.async_refresh_modbus_data()
    write_reads = [a for _, a, _ in calls]
    results.check("refresh after a write reads only the measurement registers",
                  set(write_reads) <= {300, 1200} and write_reads, f"got {write_reads}")

    # The new setpoint reaches the power reading within ~2 measurement cycles.
    target = 10 * 230 * 0.98 * 3
    t0 = time.time()
    while time.time() - t0 < 5 and abs(hub.data.get("socket_1_realPowerSum", 0) - target) > 1:
        await asyncio.sleep(0.1)
    latency = time.time() - t0
    results.check("new power visible within 3 s of the write", latency < 3, f"took {latency:.1f}s")
    log.info(f"        power {hub.data.get('socket_1_realPowerSum')} W, {latency:.1f} s after writing 10 A")

    # Busy guard: a timer tick is dropped while a read runs; a write refresh is not.
    calls.clear()
    hub._measurement_busy = True
    await hub.async_refresh_modbus_data(dt.datetime.now(dt.UTC))
    dropped = len(calls)
    await hub.async_refresh_modbus_data()
    after_write = len(calls)
    hub._measurement_busy = False
    results.check("timer tick dropped while busy", dropped == 0, f"{dropped} reads")
    results.check("write refresh runs while busy", after_write > 0)

    # Max current refresh: quiet while the setpoint is valid, triggered near expiry.
    before = len(max_current_refreshes)
    await asyncio.sleep(2.5)
    results.check("no max current refresh while valid time is 60 s", len(max_current_refreshes) == before)
    await sim_write(LIVE_PORT, 1, 1208, [0, 5])  # valid time 5 s < 1 s + 10 s margin
    await asyncio.sleep(2.5)
    results.check("max current refresh when valid time drops to 5 s", len(max_current_refreshes) > before)
    await sim_write(LIVE_PORT, 1, 1208, [0, 60])

    results.check("entities notified after reads", len(notified) >= 10, f"{len(notified)} notifications")

    # Removing the last entity stops both timers and closes the connection;
    # a read that arrives after that does not reopen it.
    hub.async_remove_alfen_sensor(hub._sensors[0], hub._inputs[0])
    await asyncio.sleep(0.2)
    calls.clear()
    late = await hub.read_holding_registers(1, 300, 46)
    results.check("no read after the last entity is removed",
                  late is None and await hub.read_modbus_data() is False and not hub._client.connected,
                  f"result {late!r}, connected {hub._client.connected}")


async def test_socket_state(new_mod, hass, results):
    log.info("\n=== Mode 3 state, session, charger enabled, meter age (static simulator) ===")
    hub = new_mod.AlfenModbusHub(hass, "alfen", "127.0.0.1", STATIC_PORT, 200, 30)
    await hub.read_modbus_data()

    async def set_mode3(state):
        await sim_write(STATIC_PORT, 1, 1201, string_registers(state, 10))
        await hub.read_modbus_data_measurements()
        return hub.data["socket_1_carconnected"], hub.data["socket_1_carcharging"]

    try:
        cases = [("A", 0, 0), ("A1", 0, 0), ("B1", 1, 0), ("B2", 1, 0), ("C1", 1, 0), ("C2", 1, 1),
                 ("D1", 1, 0), ("D2", 1, 1), ("E", 0, 0), ("F", 0, 0), ("", 0, 0), ("c2", 1, 1)]
        wrong = []
        for state, connected, charging in cases:
            got = await set_mode3(state)
            if got != (connected, charging):
                wrong.append(f"{state!r}: got {got}, expected {(connected, charging)}")
        results.check("car connected/charging per Mode 3 state family", not wrong, "; ".join(wrong))

        # The session runs from plug-in to unplug: a pause in charging keeps it.
        await set_mode3("A")
        await set_mode3("B1")
        start = hub.data.get("socket_1_chargingStart")
        for state in ("C2", "C1", "C2"):
            await set_mode3(state)
        results.check("session start set at plug-in and kept across a charging pause",
                      start is not None and hub.data.get("socket_1_chargingStart") is start)
        # A real charger end: Alfen reports E for a few seconds with the car
        # still plugged in. E and F must not end the session.
        # The simulated station clock stands still, so a restarted session would
        # get the same start time: check that the start is never removed.
        dropped = []
        for state in ("B2", "E", "B2", "F", "B2"):
            await set_mode3(state)
            if "socket_1_chargingStart" not in hub.data:
                dropped.append(state)
        results.check("session kept through E and F with the car plugged in", not dropped,
                      f"session start removed at {dropped}")
        await set_mode3("A")
        results.check("session start cleared at unplug", "socket_1_chargingStart" not in hub.data)
        await set_mode3("E")
        results.check("E without a car does not start a session", "socket_1_chargingStart" not in hub.data)

        await sim_write(STATIC_PORT, 1, 1210, float_registers(0.0))
        await hub.read_modbus_data_measurements()
        disabled = hub.data["socket_1_chargerenabled"]
        await sim_write(STATIC_PORT, 1, 1210, float_registers(16.0))
        await hub.read_modbus_data_measurements()
        results.check("charger enabled follows the max current setpoint (0 A -> off)",
                      disabled == 0 and hub.data["socket_1_chargerenabled"] == 1)

        await sim_write(STATIC_PORT, 1, 301, uint64_registers(0xFFFFFFFFFFFFFFFF))
        await hub.read_modbus_data_measurements()
        results.check("meter age 'not available' (all ones) reads as unknown", hub.data["socket_1_meterAge"] is None,
                      f"got {hub.data['socket_1_meterAge']!r}")
    finally:
        await sim_write(STATIC_PORT, 1, 1201, string_registers("C2", 10))
        await sim_write(STATIC_PORT, 1, 1210, float_registers(16.0))
        await sim_write(STATIC_PORT, 1, 301, uint64_registers(500))
        hub._client.close()


def test_firmware_repair(new_mod, results):
    log.info("\n=== Outdated NG9xx firmware repair issue ===")
    repairs = importlib.import_module("custom_components.alfen_modbus.repairs")
    issue = "ng9xx_firmware_outdated_e1"
    cases = [("NG910", "5.16.0-4095", True), ("NG910", "6.4.0-4210", False), ("NG910", "7.0.1-1000", False),
             ("NG910", "unknown", True), ("AHP02-60227", "2.6.0", False)]
    wrong = []
    for platform, firmware, expected in cases:
        repairs.async_check_firmware(None, "e1", platform, firmware)
        if (issue in ISSUES) != expected:
            wrong.append(f"{platform} {firmware}: issue {issue in ISSUES}")
    results.check("issue raised for NG9xx below 6.4.0 only", not wrong, "; ".join(wrong))
    repairs.async_check_firmware(None, "e1", "NG910", "5.16.0-4095")
    repairs.async_clear_firmware_issue(None, "e1")
    results.check("issue removed on unload", issue not in ISSUES)


async def test_setup_entry_intervals(new_mod, hass, results):
    log.info("\n=== async_setup_entry: measurement interval choice ===")
    await new_mod.async_setup(hass, {})
    cases = [
        ("no option (existing entry)", {}, 20),
        ("measurement 2 s", {"measurement_interval": 2}, 2),
        ("measurement above scan is capped", {"measurement_interval": 60}, 20),
    ]
    for label, extra, expected in cases:
        entry = make_entry(host="127.0.0.1", name="alfen", port=STATIC_PORT,
                           modbus_address=200, scan_interval=20, **extra)
        await new_mod.async_setup_entry(hass, entry)
        hub = entry.runtime_data
        got = hub._measurement_interval.total_seconds()
        results.check(f"{label}: {expected} s", got == expected, f"got {got}")
        results.check(f"{label}: scan stays 20 s", hub._scan_interval.total_seconds() == 20)
        hub._client.close()


async def test_identification_on_setup_and_reload(new_mod, hass, results):
    log.info("\n=== Identification at HA startup and integration reload ===")
    # Record at class level: async_setup_entry creates the hub itself.
    calls = []
    original = new_mod.AlfenModbusHub.read_holding_registers

    async def recording(self, unit, address, count):
        calls.append((unit, address, count))
        return await original(self, unit, address, count)

    new_mod.AlfenModbusHub.read_holding_registers = recording
    try:
        await new_mod.async_setup(hass, {})
        entry = make_entry(host="127.0.0.1", name="alfen_reload", port=STATIC_PORT,
                           modbus_address=200, scan_interval=20, measurement_interval=2)
        # HA startup: the entry is set up.
        await new_mod.async_setup_entry(hass, entry)
        first_hub = entry.runtime_data
        after_startup = calls.count((200, 100, 68))
        # Integration reload (also after an options change): unload, then set up again.
        await new_mod.async_unload_entry(hass, entry)
        first_hub._client.close()
        first_hub.data.clear()
        await new_mod.async_setup_entry(hass, entry)
        second_hub = entry.runtime_data
        after_reload = calls.count((200, 100, 68))
        second_hub._client.close()
    finally:
        new_mod.AlfenModbusHub.read_holding_registers = original

    results.check("identification read at startup", after_startup == 1, f"got {after_startup}")
    results.check("identification read again at reload", after_reload == 2, f"got {after_reload}")
    results.check("reload builds a new hub with the identification filled in",
                  second_hub is not first_hub and second_hub.data.get("serial") and second_hub.data.get("firmwareVersion"),
                  f"serial={second_hub.data.get('serial')!r} firmware={second_hub.data.get('firmwareVersion')!r}")
    platform = second_hub.data.get("platformType", "")
    results.check("firmware repair issue matches the simulated charger",
                  (f"ng9xx_firmware_outdated_{entry.entry_id}" in ISSUES) == ("NG9" in platform.upper()),
                  f"platform {platform!r}, issues {sorted(ISSUES)}")


async def test_identification_after_charger_restart(new_mod, hass, results):
    log.info("\n=== Identification after a charger restart (uptime goes back) ===")
    hub = new_mod.AlfenModbusHub(hass, "alfen", "127.0.0.1", STATIC_PORT, 200, 30, measurement_interval=2)
    await hub.read_modbus_data()
    old_firmware = hub.data["firmwareVersion"]
    calls = record_reads(hub)
    ident = lambda: calls.count((200, 100, 68))
    try:
        await hub.read_modbus_data_slow()
        results.check("no identification read while the charger keeps running", ident() == 0, f"got {ident()}")

        # Restart with new firmware: uptime drops, the firmware string changes.
        await sim_write(STATIC_PORT, 200, 123, string_registers("6.4.0-4210", 34))
        await sim_write(STATIC_PORT, 200, 174, uint64_registers(1000))
        await hub.read_modbus_data_slow()
        results.check("identification read once after the restart", ident() == 1, f"got {ident()}")
        results.check("new firmware version picked up", hub.data["firmwareVersion"] == "6.4.0-4210",
                      f"{old_firmware!r} -> {hub.data['firmwareVersion']!r}")
        await hub.read_modbus_data_slow()
        results.check("not read again on the next cycle", ident() == 1, f"got {ident()}")

        # Restart where the first identification read fails: retried, and the
        # rest of the slow read still completes.
        await sim_write(STATIC_PORT, 200, 174, uint64_registers(500))
        real_read = hub.read_holding_registers
        failed_once = []

        async def flaky(unit, address, count):
            if address == 100 and not failed_once:
                failed_once.append(True)
                calls.append((unit, address, count))
                return types.SimpleNamespace(isError=lambda: True)
            return await real_read(unit, address, count)

        hub.read_holding_registers = flaky
        slow_ok = await hub.read_modbus_data_slow()
        results.check("failed identification does not fail the slow read", slow_ok is True)
        results.check("identification still pending after the failure", hub._identification_pending is True)
        await hub.read_modbus_data_slow()
        results.check("identification retried and done on the next cycle",
                      hub._identification_pending is False and ident() == 3, f"reads {ident()}")
    finally:
        await sim_write(STATIC_PORT, 200, 123, string_registers("5.16.0-4095", 34))
        await sim_write(STATIC_PORT, 200, 174, uint64_registers(3600000))
        hub._client.close()


def test_config_schema(results):
    log.info("\n=== Config flow schema ===")
    flow = importlib.import_module("custom_components.alfen_modbus.config_flow")
    data = flow.DATA_SCHEMA({"host": "192.0.2.1"})
    results.check("new entry defaults measurement interval to the scan interval (30)",
                  data.get("measurement_interval") == 30 == data.get("scan_interval"), f"got {data}")
    try:
        flow.DATA_SCHEMA({"host": "192.0.2.1", "measurement_interval": 0})
        rejected = False
    except vol.Invalid:
        rejected = True
    results.check("measurement interval 0 is rejected", rejected)


async def main():
    install_ha_stubs()
    sys.path.insert(0, REPO)
    new_mod = importlib.import_module("custom_components.alfen_modbus")

    sims = [start_simulator(STATIC_PORT, True), start_simulator(LIVE_PORT, False)]
    results = Results()
    try:
        ready = await wait_for_port(STATIC_PORT) and await wait_for_port(LIVE_PORT)
        if not ready:
            log.error("Simulators did not start")
            return 1
        hass = FakeHass()
        await test_register_map(new_mod, hass, results)
        await test_request_plan(new_mod, hass, results)
        await test_timers_and_writes(new_mod, hass, results)
        await test_socket_state(new_mod, hass, results)
        test_firmware_repair(new_mod, results)
        await test_setup_entry_intervals(new_mod, hass, results)
        await test_identification_on_setup_and_reload(new_mod, hass, results)
        await test_identification_after_charger_restart(new_mod, hass, results)
        test_config_schema(results)
    finally:
        for proc in sims:
            proc.terminate()

    log.info(f"\n{results.passed} passed, {len(results.failed)} failed")
    for name in results.failed:
        log.info(f"  failed: {name}")
    return 0 if not results.failed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
