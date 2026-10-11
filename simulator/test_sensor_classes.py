"""
Tests every entity of every platform against the real Home Assistant
entity classes, with the data of a real hub read from the static simulator
(both sockets and SCN).

Covers:
  - each platform's async_setup_entry creates its entities without errors
  - unique IDs are unique per platform and sensors keep the <hub>_<key> format
  - every translation_key has a name in strings.json, and every entity name
    resolves with its placeholders filled in
  - one sensor per unit gets the expected unit, device class and state class
  - every unit in the sensor tables has a device class (except VAh, for which
    Home Assistant has none), valid for that device class
  - every state class is valid for its device class
  - every entity renders a valid state through Home Assistant's own state
    property, and every sensor with a unit has a value
  - the diagnostics download is JSON and redacts the host and serial

Usage:
    python test_sensor_classes.py         # starts its own simulator on 5023

Requires homeassistant (the minimum version in hacs.json), pymodbus >= 3.11.2
and python-dateutil. Unlike test_hub_polling.py, this test uses the real
homeassistant package and no stubs.
"""
import asyncio
import importlib
import json
import logging
import os
import sys
import types

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.sensor.const import (
    DEVICE_CLASS_STATE_CLASSES,
    DEVICE_CLASS_UNITS,
)
from homeassistant.helpers.entity_platform import PlatformData
from homeassistant.util.unit_system import METRIC_SYSTEM
from test_hub_polling import (
    FakeHass,
    Results,
    sim_write,
    start_simulator,
    wait_for_port,
)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PORT = 5023
HUB_NAME = "alfen"
PACKAGE = "custom_components.alfen_modbus"

log = logging.getLogger("hub_test")

D = SensorDeviceClass
S = SensorStateClass

# key -> (unit, device class, state class). At least one sensor per unit.
EXPECTED = {
    # The sensor from straybiker/HA-EV-Charge-Control issue 4.
    "socket_1_actualMaxCurrent": ("A", D.CURRENT, S.MEASUREMENT),
    "actualMaxCurrent": ("A", D.CURRENT, S.MEASUREMENT),
    "scnSafeCurrent": ("A", D.CURRENT, S.MEASUREMENT),
    "socket_1_VL1-N": ("V", D.VOLTAGE, S.MEASUREMENT),
    "socket_2_VL3-L1": ("V", D.VOLTAGE, S.MEASUREMENT),
    "socket_1_frequency": ("Hz", D.FREQUENCY, S.MEASUREMENT),
    "socket_1_realPowerSum": ("W", D.POWER, S.MEASUREMENT),
    "socket_1_apparantPowerSum": ("VA", D.APPARENT_POWER, S.MEASUREMENT),
    "socket_1_reactivePowerSum": ("var", D.REACTIVE_POWER, S.MEASUREMENT),
    "socket_1_realEnergyDeliveredSum": ("Wh", D.ENERGY, S.TOTAL_INCREASING),
    "socket_1_currentSession": ("Wh", D.ENERGY, S.TOTAL_INCREASING),
    "socket_1_reactiveEnergySum": ("varh", D.REACTIVE_ENERGY, S.TOTAL),
    "socket_1_apparantEnergySum": ("VAh", None, S.TOTAL_INCREASING),
    "socket_1_meterAge": ("s", D.DURATION, S.MEASUREMENT),
    "socket_1_currentSessionDuration": ("s", D.DURATION, S.MEASUREMENT),
    "scnMaxCurrentValidTimeL1": ("s", D.DURATION, S.MEASUREMENT),
    "boardTemperature": ("°C", D.TEMPERATURE, S.MEASUREMENT),
    "socket_1_powerSum": (None, D.POWER_FACTOR, S.MEASUREMENT),
    "socket_2_powerL1": (None, D.POWER_FACTOR, S.MEASUREMENT),
    "socket_1_carcharging": (None, D.ENUM, None),
    "backofficeConnected": (None, D.ENUM, None),
    "socket_1_mode3state": (None, None, None),
    "numberOfSockets": (None, None, None),
    "name": (None, None, None),
}


async def make_hub(new_mod, hass):
    hub = new_mod.AlfenModbusHub(hass, HUB_NAME, "127.0.0.1", PORT, 200, 30,
                                 read_scn=True, read_socket_2=True)
    await hub.read_modbus_data()
    hub._client.close()
    return hub


def platform_translations(strings, platform):
    """The entity translations as Home Assistant loads them for a platform."""
    return {
        f"component.alfen_modbus.entity.{platform}.{key}.{field}": text
        for key, fields in strings["entity"].get(platform, {}).items()
        for field, text in fields.items()
        if isinstance(text, str)
    }


def collector(target):
    """An async_add_entities that keeps the entities in target."""
    return lambda new, *args, **kwargs: target.extend(new)


def load_strings():
    with open(os.path.join(REPO, "custom_components", "alfen_modbus", "strings.json"), encoding="utf-8") as f:
        return json.load(f)


async def setup_platforms(new_mod, hass, hub, strings):
    """Run each platform's async_setup_entry; return {platform: [entities]}.

    Each entity gets the platform data Home Assistant gives it when it is
    added, with the translations from strings.json.
    """
    entry = types.SimpleNamespace(entry_id="e1", runtime_data=hub,
                                  data={"name": HUB_NAME, "host": "192.0.2.1", "port": 502})
    entities = {}
    for platform in new_mod.PLATFORMS:
        module = importlib.import_module(f"{PACKAGE}.{platform}")
        added = []
        await module.async_setup_entry(hass, entry, collector(added))
        platform_data = PlatformData(hass, domain=platform, platform_name="alfen_modbus")
        platform_data.platform_translations = platform_translations(strings, platform)
        platform_data.default_language_platform_translations = platform_data.platform_translations
        for entity in added:
            entity.platform_data = platform_data
        entities[platform] = added
    return entry, entities


def test_entities(entities, strings, results):
    log.info("\n=== Entities per platform ===")
    for platform, items in entities.items():
        log.info(f"        {platform}: {len(items)} entities")
    results.check("every platform creates entities", all(entities.values()),
                  f"empty: {[p for p, e in entities.items() if not e]}")

    # The entity registry keys on (platform, unique ID), so a sensor and a
    # binary sensor may share one.
    duplicates = []
    for platform, items in entities.items():
        ids = [e.unique_id for e in items]
        duplicates += sorted({f"{platform}.{i}" for i in ids if ids.count(i) > 1})
    results.check("unique IDs are unique within each platform", not duplicates, f"duplicates {duplicates}")

    bad_id = [s._key for s in entities["sensor"] if s.unique_id != f"{HUB_NAME}_{s._key}"]
    results.check("sensor unique IDs keep the <hub>_<key> format", not bad_id, f"changed: {bad_id}")

    names = strings["entity"]
    missing = sorted({f"{platform}.{e.translation_key}" for platform, items in entities.items()
                      for e in items if e.translation_key
                      and e.translation_key not in names.get(platform, {})})
    results.check("every translation_key has a name in strings.json", not missing, f"missing {missing}")

    unnamed = [f"{platform}.{e.translation_key}={e.name!r}" for platform, items in entities.items()
               for e in items if not isinstance(e.name, str) or not e.name or "{" in e.name]
    results.check("every entity name resolves, placeholders filled in", not unnamed, f"bad: {unnamed[:8]}")
    socket_2 = [e.name for e in entities["sensor"] if e._key == "socket_2_VL1-N"]
    log.info(f"        example names: {entities['sensor'][0].name!r}, {socket_2}")


def test_sensor_classes(sensor_mod, sensors, results):
    log.info("\n=== Unit, device class and state class per sensor ===")
    for key, (unit, device_class, state_class) in EXPECTED.items():
        sensor = sensors.get(key)
        got = sensor and (sensor.native_unit_of_measurement, sensor.device_class, sensor.state_class)
        results.check(f"{key}: {unit} -> {device_class}, {state_class}",
                      got == (unit, device_class, state_class), f"got {got}")

    units = {s.native_unit_of_measurement for s in sensors.values()} - {None}
    no_class = sorted(u for u in units if u not in sensor_mod.UNIT_CLASSES)
    results.check("every unit is in the unit table", not no_class, f"missing {no_class}")
    without_device_class = sorted({s.native_unit_of_measurement for s in sensors.values()
                                   if s.native_unit_of_measurement and s.device_class is None})
    results.check("only VAh has no device class", without_device_class == ["VAh"],
                  f"got {without_device_class}")

    bad_unit = [k for k, s in sensors.items()
                if s.device_class and s.device_class is not D.ENUM
                and s.native_unit_of_measurement not in DEVICE_CLASS_UNITS[s.device_class]]
    results.check("every unit is valid for its device class", not bad_unit, f"invalid: {bad_unit}")

    bad_state_class = [k for k, s in sensors.items()
                       if s.device_class and s.state_class
                       and s.state_class not in DEVICE_CLASS_STATE_CLASSES[s.device_class]]
    results.check("every state class is valid for its device class", not bad_state_class,
                  f"invalid: {bad_state_class}")


def test_states(hass, entities, sensors, results):
    log.info("\n=== States through Home Assistant (static simulator) ===")
    errors, wrong_type, with_value, total = [], [], 0, 0
    for platform, items in entities.items():
        for i, entity in enumerate(items):
            total += 1
            entity.hass = hass
            entity.entity_id = f"{platform}.{HUB_NAME}_{i}"
            try:
                state = entity.state
            except Exception as err:  # noqa: BLE001 - report every failing entity
                errors.append(f"{platform} {entity.translation_key}: {type(err).__name__}: {err}")
                continue
            if state is None:
                continue
            with_value += 1
            if platform == "sensor" and (entity.state_class is not None or entity.native_unit_of_measurement is not None) \
                    and not isinstance(state, (int, float)):
                wrong_type.append(f"{entity._key}={state!r}")
    results.check("every entity gives a state that Home Assistant accepts", not errors, "; ".join(errors))
    results.check("every sensor with a unit or state class gives a number", not wrong_type, ", ".join(wrong_type))
    log.info(f"        {with_value} of {total} entities have a value")

    no_value = sorted(k for k, s in sensors.items() if s.native_unit_of_measurement and s.state is None)
    results.check("every sensor with a unit has a value", not no_value, f"no value: {no_value}")

    duration = sensors["socket_1_currentSessionDuration"]
    results.check("session duration renders as seconds",
                  isinstance(duration.state, int) and duration.unit_of_measurement == "s",
                  f"got {duration.state!r} {duration.unit_of_measurement!r}")
    results.check("actual applied max current renders in A",
                  sensors["socket_1_actualMaxCurrent"].state == 16.0
                  and sensors["socket_1_actualMaxCurrent"].unit_of_measurement == "A")
    results.check("car charging renders as on/off", sensors["socket_1_carcharging"].state == "on",
                  f"got {sensors['socket_1_carcharging'].state!r}")


async def test_diagnostics(hass, entry, results):
    log.info("\n=== Diagnostics ===")
    diagnostics = importlib.import_module(f"{PACKAGE}.diagnostics")
    data = await diagnostics.async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(data)
    results.check("diagnostics are JSON", bool(text))
    results.check("host and serial are redacted",
                  data["entry_data"]["host"] == "**REDACTED**" and data["hub_data"]["serial"] == "**REDACTED**")


async def main():
    sys.path.insert(0, REPO)
    new_mod = importlib.import_module(PACKAGE)
    sensor_mod = importlib.import_module(f"{PACKAGE}.sensor")
    strings = load_strings()

    results = Results()
    sim = start_simulator(PORT, True)
    try:
        if not await wait_for_port(PORT):
            log.error("Simulator did not start")
            return 1
        # The simulator reports one socket; report two so socket 2 is read too.
        await sim_write(PORT, 200, 1105, [2])
        hass = FakeHass()
        hass.config = types.SimpleNamespace(units=METRIC_SYSTEM)
        hub = await make_hub(new_mod, hass)
        entry, entities = await setup_platforms(new_mod, hass, hub, strings)
        sensors = {s._key: s for s in entities["sensor"]}

        test_entities(entities, strings, results)
        test_sensor_classes(sensor_mod, sensors, results)
        test_states(hass, entities, sensors, results)
        await test_diagnostics(hass, entry, results)
    finally:
        sim.terminate()

    log.info(f"\n{results.passed} passed, {len(results.failed)} failed")
    for name in results.failed:
        log.info(f"  failed: {name}")
    return 0 if not results.failed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
