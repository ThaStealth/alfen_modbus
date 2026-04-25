"""
Test script to connect to a real Alfen charger and read all values.

Usage:
    python test_real_alfen.py

Configuration:
    Edit local_config.py to set ALFEN_HOST and ALFEN_PORT
"""
import logging
import struct
from pymodbus.client import ModbusTcpClient

# Import local config (gitignored)
try:
    from local_config import ALFEN_HOST, ALFEN_PORT
except ImportError:
    print("ERROR: local_config.py not found!")
    print("Create local_config.py with:")
    print('  ALFEN_HOST = "YOUR_CHARGER_IP"')
    print('  ALFEN_PORT = 502')
    exit(1)

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger()

# Unit addresses
ADDRESS_PRODUCT = 200
ADDRESS_SOCKET_1 = 1
ADDRESS_SOCKET_2 = 2


def decode_string(registers, offset, length):
    """Decode string from registers."""
    data = b''
    for i in range(length):
        if offset + i < len(registers):
            data += struct.pack('>H', registers[offset + i])
    return data.partition(b'\x00')[0].decode('utf-8', errors='ignore')


def decode_float32(registers, offset):
    """Decode float32 from 2 registers."""
    if offset + 1 >= len(registers):
        return None
    data = struct.pack('>HH', registers[offset], registers[offset + 1])
    return struct.unpack('>f', data)[0]


def decode_float64(registers, offset):
    """Decode float64 from 4 registers."""
    if offset + 3 >= len(registers):
        return None
    data = struct.pack('>HHHH', registers[offset], registers[offset + 1],
                       registers[offset + 2], registers[offset + 3])
    return struct.unpack('>d', data)[0]


def decode_uint16(registers, offset):
    """Decode uint16 from 1 register."""
    if offset >= len(registers):
        return None
    return registers[offset]


def decode_uint32(registers, offset):
    """Decode uint32 from 2 registers."""
    if offset + 1 >= len(registers):
        return None
    data = struct.pack('>HH', registers[offset], registers[offset + 1])
    return struct.unpack('>I', data)[0]


def decode_int16(registers, offset):
    """Decode int16 from 1 register."""
    if offset >= len(registers):
        return None
    val = registers[offset]
    if val >= 0x8000:
        val -= 0x10000
    return val


def read_product_info(client):
    """Read product/station information from Unit 200."""
    log.info("=" * 60)
    log.info("PRODUCT/STATION INFORMATION (Unit 200)")
    log.info("=" * 60)
    
    # Read identification registers 100-178
    result = client.read_holding_registers(address=100, count=79, device_id=ADDRESS_PRODUCT)
    if result.isError():
        log.error(f"Failed to read product info: {result}")
        return
    
    regs = result.registers
    
    log.info(f"Name:              {decode_string(regs, 0, 17)}")
    log.info(f"Manufacturer:      {decode_string(regs, 17, 5)}")
    log.info(f"Modbus Version:    {decode_uint16(regs, 22)}")
    log.info(f"Firmware:          {decode_string(regs, 23, 17)}")
    log.info(f"Platform:          {decode_string(regs, 40, 17)}")
    log.info(f"Serial:            {decode_string(regs, 57, 11)}")
    
    year = decode_int16(regs, 68)
    month = decode_int16(regs, 69)
    day = decode_int16(regs, 70)
    hour = decode_int16(regs, 71)
    minute = decode_int16(regs, 72)
    second = decode_int16(regs, 73)
    log.info(f"Station Time:      {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}")
    
    # Read station status 1100-1105
    result = client.read_holding_registers(address=1100, count=6, device_id=ADDRESS_PRODUCT)
    if result.isError():
        log.error(f"Failed to read station status: {result}")
        return
    
    regs = result.registers
    log.info("")
    log.info("Station Status:")
    log.info(f"  Max Current:     {decode_float32(regs, 0):.1f} A")
    log.info(f"  Temperature:     {decode_float32(regs, 2):.1f} °C")
    log.info(f"  Backoffice:      {'Connected' if decode_uint16(regs, 4) else 'Disconnected'}")
    log.info(f"  Sockets:         {decode_uint16(regs, 5)}")


def read_socket_info(client, socket_id):
    """Read socket measurement and status from Unit 1 or 2."""
    log.info("")
    log.info("=" * 60)
    log.info(f"SOCKET {socket_id} MEASUREMENTS (Unit {socket_id})")
    log.info("=" * 60)
    
    # Read meter registers 300-424 (125 registers)
    result = client.read_holding_registers(address=300, count=125, device_id=socket_id)
    if result.isError():
        log.error(f"Failed to read socket {socket_id} meters: {result}")
        return False
    
    regs = result.registers
    
    log.info("Meter Info:")
    log.info(f"  State:           {decode_uint16(regs, 0)}")
    log.info(f"  Age:             {decode_uint16(regs, 1)} ms")
    log.info(f"  Type:            {decode_uint16(regs, 5)}")
    
    log.info("")
    log.info("Voltages (V):")
    log.info(f"  L1-N:            {decode_float32(regs, 6):.2f}")
    log.info(f"  L2-N:            {decode_float32(regs, 8):.2f}")
    log.info(f"  L3-N:            {decode_float32(regs, 10):.2f}")
    log.info(f"  L1-L2:           {decode_float32(regs, 12):.2f}")
    log.info(f"  L2-L3:           {decode_float32(regs, 14):.2f}")
    log.info(f"  L3-L1:           {decode_float32(regs, 16):.2f}")
    
    log.info("")
    log.info("Currents (A):")
    log.info(f"  N:               {decode_float32(regs, 18):.2f}")
    log.info(f"  L1:              {decode_float32(regs, 20):.2f}")
    log.info(f"  L2:              {decode_float32(regs, 22):.2f}")
    log.info(f"  L3:              {decode_float32(regs, 24):.2f}")
    log.info(f"  Sum:             {decode_float32(regs, 26):.2f}")
    
    log.info("")
    log.info("Power Factor:")
    log.info(f"  L1:              {decode_float32(regs, 28):.3f}")
    log.info(f"  L2:              {decode_float32(regs, 30):.3f}")
    log.info(f"  L3:              {decode_float32(regs, 32):.3f}")
    log.info(f"  Sum:             {decode_float32(regs, 34):.3f}")
    
    log.info("")
    log.info(f"Frequency:         {decode_float32(regs, 36):.2f} Hz")
    
    log.info("")
    log.info("Real Power (W):")
    log.info(f"  L1:              {decode_float32(regs, 38):.2f}")
    log.info(f"  L2:              {decode_float32(regs, 40):.2f}")
    log.info(f"  L3:              {decode_float32(regs, 42):.2f}")
    log.info(f"  Sum:             {decode_float32(regs, 44):.2f}")
    
    log.info("")
    log.info("Apparent Power (VA):")
    log.info(f"  L1:              {decode_float32(regs, 46):.2f}")
    log.info(f"  L2:              {decode_float32(regs, 48):.2f}")
    log.info(f"  L3:              {decode_float32(regs, 50):.2f}")
    log.info(f"  Sum:             {decode_float32(regs, 52):.2f}")
    
    log.info("")
    log.info("Reactive Power (VAr):")
    log.info(f"  L1:              {decode_float32(regs, 54):.2f}")
    log.info(f"  L2:              {decode_float32(regs, 56):.2f}")
    log.info(f"  L3:              {decode_float32(regs, 58):.2f}")
    log.info(f"  Sum:             {decode_float32(regs, 60):.2f}")
    
    log.info("")
    log.info("Real Energy Delivered (Wh):")
    log.info(f"  L1:              {decode_float64(regs, 62):.2f}")
    log.info(f"  L2:              {decode_float64(regs, 66):.2f}")
    log.info(f"  L3:              {decode_float64(regs, 70):.2f}")
    log.info(f"  Sum:             {decode_float64(regs, 74):.2f}")
    
    log.info("")
    log.info("Real Energy Consumed (Wh):")
    log.info(f"  L1:              {decode_float64(regs, 78):.2f}")
    log.info(f"  L2:              {decode_float64(regs, 82):.2f}")
    log.info(f"  L3:              {decode_float64(regs, 86):.2f}")
    log.info(f"  Sum:             {decode_float64(regs, 90):.2f}")
    
    log.info("")
    log.info("Apparent Energy (VAh):")
    log.info(f"  L1:              {decode_float64(regs, 92):.2f}")
    log.info(f"  L2:              {decode_float64(regs, 96):.2f}")
    log.info(f"  L3:              {decode_float64(regs, 100):.2f}")
    log.info(f"  Sum:             {decode_float64(regs, 104):.2f}")
    
    log.info("")
    log.info("Reactive Energy (VArh):")
    log.info(f"  L1:              {decode_float64(regs, 108):.2f}")
    log.info(f"  L2:              {decode_float64(regs, 112):.2f}")
    log.info(f"  L3:              {decode_float64(regs, 116):.2f}")
    log.info(f"  Sum:             {decode_float64(regs, 120):.2f}")
    
    # Read socket status 1200-1215
    result = client.read_holding_registers(address=1200, count=16, device_id=socket_id)
    if result.isError():
        log.error(f"Failed to read socket {socket_id} status: {result}")
        return False
    
    regs = result.registers
    
    log.info("")
    log.info("Socket Status:")
    log.info(f"  Availability:    {'Operative' if decode_uint16(regs, 0) else 'Inoperative'}")
    log.info(f"  Mode 3 State:    {decode_string(regs, 1, 5)}")
    log.info(f"  Actual Max I:    {decode_float32(regs, 6):.2f} A")
    log.info(f"  Valid Time:      {decode_uint32(regs, 8)} s")
    log.info(f"  Set Max I:       {decode_float32(regs, 10):.2f} A")
    log.info(f"  Safe Current:    {decode_float32(regs, 12):.2f} A")
    log.info(f"  SP Accounted:    {decode_uint16(regs, 14)}")
    log.info(f"  Charge Phases:   {decode_uint16(regs, 15)}")
    
    return True


def main():
    log.info(f"Connecting to Alfen charger at {ALFEN_HOST}:{ALFEN_PORT}...")
    
    client = ModbusTcpClient(host=ALFEN_HOST, port=ALFEN_PORT)
    
    if not client.connect():
        log.error("Failed to connect!")
        return
    
    log.info("Connected successfully!\n")
    
    try:
        read_product_info(client)
        read_socket_info(client, ADDRESS_SOCKET_1)
        # Uncomment to read socket 2:
        # read_socket_info(client, ADDRESS_SOCKET_2)
    finally:
        client.close()
        log.info("")
        log.info("Connection closed.")


if __name__ == "__main__":
    main()
