"""
Test script for Alfen Eve Single Pro Modbus Simulator

Verifies the simulator responds correctly with expected values.
"""
import asyncio
import logging
import struct
import argparse
from pymodbus.client import AsyncModbusTcpClient

# Default Configuration - matches real Alfen hardware
DEFAULT_PORT = 502
HOST = "127.0.0.1"

# Logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)

def to_bytes(registers):
    """Converts a list of 16-bit registers to bytes (Big Endian)."""
    return b''.join(r.to_bytes(2, 'big') for r in registers)

def decode_string(registers, length):
    """Decodes string from registers."""
    b = to_bytes(registers)
    return b[:length].decode('utf-8').strip('\x00')

def decode_float(registers):
    """Decodes float32 from 2 registers."""
    return struct.unpack('>f', to_bytes(registers))[0]

async def run_test(port):
    """Run verification tests against the simulator."""
    client = AsyncModbusTcpClient(HOST, port=port)
    await client.connect()
    
    if not client.connected:
        log.error("Failed to connect to simulator")
        return False

    success = True

    # =========================================================================
    # Test 1: Product Information (Unit 200)
    # =========================================================================
    log.info("=" * 60)
    log.info("Testing Unit 200 (Product/Station)")
    log.info("=" * 60)
    
    # Read Product Name (register 100, 17 registers for 34 bytes)
    rr = await client.read_holding_registers(100, count=17, device_id=200)
    if rr.isError():
        log.error(f"Failed to read product name: {rr}")
        success = False
    else:
        name = decode_string(rr.registers, 34)
        log.info(f"Product Name: '{name}'")
        if "Alfen" not in name:
            log.error(f"Expected product name to contain 'Alfen'")
            success = False
        else:
            log.info("✓ Product name verified")
    
    # Read Manufacturer
    rr = await client.read_holding_registers(117, count=5, device_id=200)
    if not rr.isError():
        manufacturer = decode_string(rr.registers, 10)
        log.info(f"Manufacturer: '{manufacturer}'")
    
    # Read Firmware Version
    rr = await client.read_holding_registers(123, count=17, device_id=200)
    if not rr.isError():
        firmware = decode_string(rr.registers, 34)
        log.info(f"Firmware: '{firmware}'")
    
    # Read Station Status
    rr = await client.read_holding_registers(1100, count=6, device_id=200)
    if not rr.isError():
        max_current = decode_float(rr.registers[0:2])
        temperature = decode_float(rr.registers[2:4])
        backoffice = rr.registers[4]
        sockets = rr.registers[5]
        log.info(f"Station Max Current: {max_current:.1f}A")
        log.info(f"Board Temperature: {temperature:.1f}°C")
        log.info(f"Backoffice Connected: {backoffice}")
        log.info(f"Number of Sockets: {sockets}")

    # =========================================================================
    # Test 2: Socket Measurements (Unit 1)
    # =========================================================================
    log.info("")
    log.info("=" * 60)
    log.info("Testing Unit 1 (Socket 1)")
    log.info("=" * 60)
    
    # Read Voltages L-N (registers 306-310)
    rr = await client.read_holding_registers(306, count=6, device_id=1)
    if rr.isError():
        log.error(f"Failed to read voltages: {rr}")
        success = False
    else:
        v_l1n = decode_float(rr.registers[0:2])
        v_l2n = decode_float(rr.registers[2:4])
        v_l3n = decode_float(rr.registers[4:6])
        log.info(f"Voltage L1-N: {v_l1n:.1f}V")
        log.info(f"Voltage L2-N: {v_l2n:.1f}V")
        log.info(f"Voltage L3-N: {v_l3n:.1f}V")
        
        # Verify voltages are in realistic range
        if not (220 < v_l1n < 245):
            log.error(f"Voltage L1-N out of expected range (220-245V)")
            success = False
        else:
            log.info("✓ Voltages verified")
    
    # Read Currents (registers 318-326)
    rr = await client.read_holding_registers(318, count=10, device_id=1)
    if not rr.isError():
        i_n = decode_float(rr.registers[0:2])
        i_l1 = decode_float(rr.registers[2:4])
        i_l2 = decode_float(rr.registers[4:6])
        i_l3 = decode_float(rr.registers[6:8])
        i_sum = decode_float(rr.registers[8:10])
        log.info(f"Current N: {i_n:.2f}A, L1: {i_l1:.1f}A, L2: {i_l2:.1f}A, L3: {i_l3:.1f}A, Sum: {i_sum:.1f}A")
    
    # Read Power (registers 338-344)
    rr = await client.read_holding_registers(338, count=8, device_id=1)
    if not rr.isError():
        p_l1 = decode_float(rr.registers[0:2])
        p_l2 = decode_float(rr.registers[2:4])
        p_l3 = decode_float(rr.registers[4:6])
        p_sum = decode_float(rr.registers[6:8])
        log.info(f"Power L1: {p_l1:.0f}W, L2: {p_l2:.0f}W, L3: {p_l3:.0f}W, Sum: {p_sum:.0f}W")
    
    # Read Frequency (register 336)
    rr = await client.read_holding_registers(336, count=2, device_id=1)
    if not rr.isError():
        freq = decode_float(rr.registers)
        log.info(f"Frequency: {freq:.2f}Hz")

    # =========================================================================
    # Test 3: Control Logic
    # =========================================================================
    log.info("")
    log.info("=" * 60)
    log.info("Testing Control Logic")
    log.info("=" * 60)
    
    target_current = 12.5
    
    # Encode float to registers
    b = struct.pack('>f', target_current)
    payload = [int.from_bytes(b[i:i+2], 'big') for i in range(0, len(b), 2)]
    
    log.info(f"Writing Max Current {target_current}A to register 1210...")
    wr = await client.write_registers(1210, payload, device_id=1)
    if wr.isError():
        log.error(f"Failed to write max current: {wr}")
        success = False
    else:
        log.info("✓ Write successful")
        
        # Wait for simulator to mirror value
        await asyncio.sleep(2)
        
        # Read back Actual Applied (register 1206)
        rr = await client.read_holding_registers(1206, count=2, device_id=1)
        if rr.isError():
            log.error(f"Failed to read actual max current: {rr}")
            success = False
        else:
            actual_current = decode_float(rr.registers)
            log.info(f"Actual Applied Max Current: {actual_current:.1f}A")
            if abs(actual_current - target_current) >= 0.1:
                log.error(f"Expected ~{target_current}A, got {actual_current}A")
                success = False
            else:
                log.info("✓ Control logic verified: 1210 → 1206 mirroring works!")

    client.close()
    
    log.info("")
    log.info("=" * 60)
    if success:
        log.info("=== ALL TESTS PASSED ===")
    else:
        log.error("=== SOME TESTS FAILED ===")
    log.info("=" * 60)
    
    return success

def main():
    parser = argparse.ArgumentParser(description='Test Alfen Eve Simulator')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_PORT,
                        help=f'TCP port to connect to (default: {DEFAULT_PORT})')
    args = parser.parse_args()
    
    result = asyncio.run(run_test(args.port))
    exit(0 if result else 1)

if __name__ == "__main__":
    main()
