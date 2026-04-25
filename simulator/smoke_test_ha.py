"""
HA Integration Smoke Tests for Alfen Eve Simulator

These tests replicate exactly how the Home Assistant alfen_modbus integration
reads data from the charger. If these tests pass, the HA integration should
work correctly against the simulator.

Based on: alfen_modbus/custom_components/alfen_modbus/__init__.py
"""
import asyncio
import logging
import struct
import argparse
from pymodbus.client import AsyncModbusTcpClient

# Configuration - matches HA integration defaults
DEFAULT_PORT = 502
HOST = "127.0.0.1"
DEFAULT_MODBUS_ADDRESS = 200  # Product/Station unit

logging.basicConfig()
log = logging.getLogger("smoke_test")
log.setLevel(logging.INFO)

# ============================================================================
# Decoding utilities (matching HA component's decode methods)
# ============================================================================

def decode_string(registers, offset, count):
    """Decode STRING from registers at offset."""
    regs = registers[offset:offset + count]
    b = b''.join(r.to_bytes(2, 'big') for r in regs)
    return b.decode('utf-8', errors='ignore').strip('\x00')

def decode_float32(registers, offset):
    """Decode FLOAT32 from 2 registers at offset."""
    regs = registers[offset:offset + 2]
    b = b''.join(r.to_bytes(2, 'big') for r in regs)
    return struct.unpack('>f', b)[0]

def decode_float64(registers, offset):
    """Decode FLOAT64 from 4 registers at offset."""
    regs = registers[offset:offset + 4]
    b = b''.join(r.to_bytes(2, 'big') for r in regs)
    return struct.unpack('>d', b)[0]

def decode_uint16(registers, offset):
    """Decode UINT16 from 1 register at offset."""
    return registers[offset]

def decode_int16(registers, offset):
    """Decode INT16 from 1 register at offset."""
    val = registers[offset]
    return val if val < 0x8000 else val - 0x10000

def decode_uint32(registers, offset):
    """Decode UINT32 from 2 registers at offset."""
    regs = registers[offset:offset + 2]
    return (regs[0] << 16) | regs[1]

def decode_uint64(registers, offset):
    """Decode UINT64 from 4 registers at offset."""
    regs = registers[offset:offset + 4]
    b = b''.join(r.to_bytes(2, 'big') for r in regs)
    return struct.unpack('>Q', b)[0]

# ============================================================================
# Smoke Tests - Replicating HA Component Behavior
# ============================================================================

class SmokeTestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def check(self, name, condition, expected=None, actual=None):
        if condition:
            self.passed += 1
            log.info(f"  ✓ {name}")
        else:
            self.failed += 1
            msg = f"  ✗ {name}"
            if expected is not None:
                msg += f" (expected: {expected}, got: {actual})"
            log.error(msg)
            self.errors.append(msg)
    
    def check_range(self, name, value, min_val, max_val):
        if min_val <= value <= max_val:
            self.passed += 1
            log.info(f"  ✓ {name}: {value}")
        else:
            self.failed += 1
            msg = f"  ✗ {name}: {value} not in range [{min_val}, {max_val}]"
            log.error(msg)
            self.errors.append(msg)


async def test_product_data(client, unit, result):
    """
    Tests read_modbus_data_product() - Registers 100-178 (79 registers)
    
    This is called from: read_modbus_data_product() in __init__.py
    """
    log.info("\n=== Test: Product Data (Unit %d, Registers 100-178) ===" % unit)
    
    rr = await client.read_holding_registers(100, count=79, device_id=unit)
    if rr.isError():
        log.error(f"Failed to read product data: {rr}")
        result.failed += 1
        return
    
    regs = rr.registers
    
    # Decode exactly as HA component does
    name = decode_string(regs, 0, 17)
    manufacturer = decode_string(regs, 17, 5)
    modbus_table_version = decode_int16(regs, 22)
    firmware_version = decode_string(regs, 23, 17)
    platform_type = decode_string(regs, 40, 17)
    serial = decode_string(regs, 57, 11)
    
    # Time fields
    year = decode_int16(regs, 68)
    month = decode_int16(regs, 69)
    day = decode_int16(regs, 70)
    hour = decode_int16(regs, 71)
    minute = decode_int16(regs, 72)
    second = decode_int16(regs, 73)
    uptime = decode_uint64(regs, 74)
    utc_offset = decode_int16(regs, 78)
    
    log.info(f"  Name: '{name}'")
    log.info(f"  Manufacturer: '{manufacturer}'")
    log.info(f"  Modbus Table Version: {modbus_table_version}")
    log.info(f"  Firmware: '{firmware_version}'")
    log.info(f"  Platform: '{platform_type}'")
    log.info(f"  Serial: '{serial}'")
    log.info(f"  Station Time: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d} (UTC{utc_offset:+d})")
    log.info(f"  Uptime: {uptime}ms")
    
    # Validations
    result.check("Name contains 'Alfen'", "Alfen" in name, "contains 'Alfen'", name)
    result.check("Manufacturer is 'Alfen'", "Alfen" in manufacturer, "contains 'Alfen'", manufacturer)
    result.check("Modbus Table Version > 0", modbus_table_version > 0, "> 0", modbus_table_version)
    result.check("Firmware not empty", len(firmware_version) > 0)
    result.check("Platform not empty", len(platform_type) > 0)
    result.check("Serial not empty", len(serial) > 0)


async def test_station_data(client, unit, result):
    """
    Tests read_modbus_data_station() - Registers 1100-1105 (6 registers)
    
    This is called from: read_modbus_data_station() in __init__.py
    """
    log.info("\n=== Test: Station Status (Unit %d, Registers 1100-1105) ===" % unit)
    
    rr = await client.read_holding_registers(1100, count=6, device_id=unit)
    if rr.isError():
        log.error(f"Failed to read station data: {rr}")
        result.failed += 1
        return
    
    regs = rr.registers
    
    # Decode exactly as HA component does
    actual_max_current = round(decode_float32(regs, 0), 2)
    board_temperature = round(decode_float32(regs, 2), 2)
    backoffice_connected = decode_uint16(regs, 4)
    number_of_sockets = decode_uint16(regs, 5)
    
    log.info(f"  Actual Max Current: {actual_max_current}A")
    log.info(f"  Board Temperature: {board_temperature}°C")
    log.info(f"  Backoffice Connected: {backoffice_connected}")
    log.info(f"  Number of Sockets: {number_of_sockets}")
    
    # Validations
    result.check_range("Actual Max Current", actual_max_current, 0, 64)
    result.check_range("Board Temperature", board_temperature, -20, 80)
    result.check("Backoffice Connected is 0 or 1", backoffice_connected in [0, 1])
    result.check_range("Number of Sockets", number_of_sockets, 1, 2)


async def test_socket_energy_data(client, socket_id, result):
    """
    Tests read_modbus_data_socket() - Registers 300-424 (125 registers)
    
    This is called from: read_modbus_data_socket() in __init__.py
    Socket 1 uses unit=1, Socket 2 uses unit=2
    """
    log.info("\n=== Test: Socket %d Energy Data (Unit %d, Registers 300-424) ===" % (socket_id, socket_id))
    
    rr = await client.read_holding_registers(300, count=125, device_id=socket_id)
    if rr.isError():
        log.error(f"Failed to read socket {socket_id} energy data: {rr}")
        result.failed += 1
        return
    
    regs = rr.registers
    
    # Decode exactly as HA component does (offsets from register 300)
    meter_state = decode_uint16(regs, 0)
    meter_age = decode_uint16(regs, 1)  # Actually UINT16 for first part
    meter_type = decode_uint16(regs, 5)
    
    v_l1n = round(decode_float32(regs, 6), 2)
    v_l2n = round(decode_float32(regs, 8), 2)
    v_l3n = round(decode_float32(regs, 10), 2)
    
    v_l1l2 = round(decode_float32(regs, 12), 2)
    v_l2l3 = round(decode_float32(regs, 14), 2)
    v_l3l1 = round(decode_float32(regs, 16), 2)
    
    i_n = round(decode_float32(regs, 18), 2)
    i_l1 = round(decode_float32(regs, 20), 2)
    i_l2 = round(decode_float32(regs, 22), 2)
    i_l3 = round(decode_float32(regs, 24), 2)
    i_sum = round(decode_float32(regs, 26), 2)
    
    pf_l1 = round(decode_float32(regs, 28), 2)
    pf_l2 = round(decode_float32(regs, 30), 2)
    pf_l3 = round(decode_float32(regs, 32), 2)
    pf_sum = round(decode_float32(regs, 34), 2)
    
    frequency = round(decode_float32(regs, 36), 2)
    
    p_l1 = round(decode_float32(regs, 38), 2)
    p_l2 = round(decode_float32(regs, 40), 2)
    p_l3 = round(decode_float32(regs, 42), 2)
    p_sum = round(decode_float32(regs, 44), 2)
    
    e_delivered_sum = round(decode_float64(regs, 74), 2)
    
    log.info(f"  Meter State: {meter_state}")
    log.info(f"  Voltages L-N: {v_l1n}V, {v_l2n}V, {v_l3n}V")
    log.info(f"  Voltages L-L: {v_l1l2}V, {v_l2l3}V, {v_l3l1}V")
    log.info(f"  Currents: N={i_n}A, L1={i_l1}A, L2={i_l2}A, L3={i_l3}A, Sum={i_sum}A")
    log.info(f"  Power Factors: {pf_l1}, {pf_l2}, {pf_l3}, Sum={pf_sum}")
    log.info(f"  Frequency: {frequency}Hz")
    log.info(f"  Real Power: L1={p_l1}W, L2={p_l2}W, L3={p_l3}W, Sum={p_sum}W")
    log.info(f"  Energy Delivered Sum: {e_delivered_sum}Wh")
    
    # Validations
    result.check("Meter State defined", meter_state in range(16))
    result.check_range("Voltage L1-N", v_l1n, 200, 260)
    result.check_range("Voltage L2-N", v_l2n, 200, 260)
    result.check_range("Voltage L3-N", v_l3n, 200, 260)
    result.check_range("Voltage L1-L2", v_l1l2, 350, 450)
    result.check_range("Frequency", frequency, 49.5, 50.5)
    result.check("Current N >= 0", i_n >= 0)
    result.check("Current Sum >= 0", i_sum >= 0)
    result.check_range("Power Factor L1", pf_l1, 0, 1.1)
    result.check("Energy Delivered >= 0", e_delivered_sum >= 0)


async def test_socket_status_data(client, socket_id, result):
    """
    Tests read_modbus_data_socket() - Registers 1200-1215 (16 registers)
    
    This is the second part of read_modbus_data_socket() in __init__.py
    """
    log.info("\n=== Test: Socket %d Status (Unit %d, Registers 1200-1215) ===" % (socket_id, socket_id))
    
    rr = await client.read_holding_registers(1200, count=16, device_id=socket_id)
    if rr.isError():
        log.error(f"Failed to read socket {socket_id} status data: {rr}")
        result.failed += 1
        return
    
    regs = rr.registers
    
    # Decode exactly as HA component does (offsets from register 1200)
    availability = decode_uint16(regs, 0)
    mode3_state = decode_string(regs, 1, 5)
    actual_max_current = round(decode_float32(regs, 6), 2)
    valid_time = decode_uint32(regs, 8)
    max_current = round(decode_float32(regs, 10), 2)
    safe_current = round(decode_float32(regs, 12), 2)
    setpoint_accounted = decode_uint16(regs, 14)
    charge_phases = decode_uint16(regs, 15)
    
    log.info(f"  Availability: {availability} ({'Operative' if availability == 1 else 'Inoperative'})")
    log.info(f"  Mode 3 State: '{mode3_state}'")
    log.info(f"  Actual Applied Max Current: {actual_max_current}A")
    log.info(f"  Max Current Valid Time: {valid_time}s")
    log.info(f"  Modbus Slave Max Current: {max_current}A")
    log.info(f"  Active Load Balancing Safe Current: {safe_current}A")
    log.info(f"  Setpoint Accounted: {setpoint_accounted}")
    log.info(f"  Charging Mode Phases: {charge_phases}")
    
    # Validations
    result.check("Availability is 0 or 1", availability in [0, 1])
    result.check("Mode 3 State not empty", len(mode3_state) > 0)
    result.check_range("Actual Applied Max Current", actual_max_current, 0, 64)
    result.check_range("Max Current", max_current, 0, 64)
    result.check_range("Safe Current", safe_current, 0, 64)
    result.check("Charge Phases is 1 or 3", charge_phases in [1, 3])
    
    # Binary sensor logic (derived from mode3_state - matches __init__.py lines 427-438)
    car_connected = 0 if mode3_state in ["A", "E", "F"] else 1
    car_charging = 1 if mode3_state in ["C2", "D2"] else 0
    
    log.info(f"  --- Binary Sensor Derivation ---")
    log.info(f"  Car Connected: {car_connected} (derived from mode3_state='{mode3_state}')")
    log.info(f"  Car Charging: {car_charging} (derived from mode3_state='{mode3_state}')")
    
    result.check("Car Connected is 0 or 1", car_connected in [0, 1])
    result.check("Car Charging is 0 or 1", car_charging in [0, 1])
    # If car is charging, it must also be connected
    if car_charging == 1:
        result.check("Charging implies connected", car_connected == 1)


async def test_write_max_current(client, socket_id, result):
    """
    Tests writing to Max Current register (1210)
    
    This replicates the write operation from the HA number entity
    """
    log.info("\n=== Test: Write Max Current (Socket %d, Register 1210) ===" % socket_id)
    
    test_current = 14.5
    
    # Encode as float32 (exactly as HA does)
    b = struct.pack('>f', test_current)
    payload = [int.from_bytes(b[i:i+2], 'big') for i in range(0, len(b), 2)]
    
    log.info(f"  Writing {test_current}A to register 1210...")
    
    wr = await client.write_registers(1210, payload, device_id=socket_id)
    if wr.isError():
        log.error(f"Failed to write max current: {wr}")
        result.failed += 1
        return
    
    result.check("Write operation succeeded", True)
    
    # Wait for simulator to update applied current
    await asyncio.sleep(2)
    
    # Read back the applied current (register 1206)
    rr = await client.read_holding_registers(1206, count=2, device_id=socket_id)
    if rr.isError():
        log.error(f"Failed to read applied max current: {rr}")
        result.failed += 1
        return
    
    applied_current = round(decode_float32(rr.registers, 0), 2)
    log.info(f"  Applied Max Current: {applied_current}A")
    
    result.check(
        "Applied current matches written value",
        abs(applied_current - test_current) < 0.1,
        test_current, applied_current
    )


async def run_smoke_tests(port):
    """Run all smoke tests."""
    log.info("=" * 70)
    log.info("Alfen Eve Simulator - HA Integration Smoke Tests")
    log.info("=" * 70)
    log.info(f"Connecting to {HOST}:{port}...")
    
    client = AsyncModbusTcpClient(HOST, port=port)
    await client.connect()
    
    if not client.connected:
        log.error("Failed to connect to simulator!")
        return False
    
    log.info("Connected successfully.\n")
    
    result = SmokeTestResult()
    
    # Run all tests (matching HA component's read_modbus_data() sequence)
    await test_product_data(client, DEFAULT_MODBUS_ADDRESS, result)
    await test_station_data(client, DEFAULT_MODBUS_ADDRESS, result)
    await test_socket_energy_data(client, 1, result)
    await test_socket_status_data(client, 1, result)
    await test_write_max_current(client, 1, result)
    
    client.close()
    
    # Summary
    log.info("\n" + "=" * 70)
    log.info("SMOKE TEST SUMMARY")
    log.info("=" * 70)
    log.info(f"  Passed: {result.passed}")
    log.info(f"  Failed: {result.failed}")
    
    if result.failed > 0:
        log.error("\nFailed tests:")
        for err in result.errors:
            log.error(err)
        log.info("=" * 70)
        return False
    else:
        log.info("\n=== ALL SMOKE TESTS PASSED ===")
        log.info("The HA integration should work correctly with this simulator.")
        log.info("=" * 70)
        return True


def main():
    parser = argparse.ArgumentParser(description='HA Integration Smoke Tests')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_PORT,
                        help=f'TCP port (default: {DEFAULT_PORT})')
    args = parser.parse_args()
    
    success = asyncio.run(run_smoke_tests(args.port))
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
