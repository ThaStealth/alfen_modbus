"""
Alfen Eve Single Pro Modbus TCP Simulator

Simulates the Modbus TCP registers of an Alfen Eve Single Pro charging station.
Designed to match real hardware specifications for testing the alfen_modbus integration.

Default Port: 502 (standard Modbus TCP)
Unit Addresses:
  - 200: Product/Station information
  - 1: Socket 1 measurements and control
  - 2: Socket 2 measurements and control
  
Register addressing:
  ModbusDeviceContext adds +1 to read addresses internally, so we store data
  at block[N] to have it appear at register N+1 from client's perspective.
  Therefore, to have client read register N, we store at block[N-1].
"""
import asyncio
import logging
import struct
import argparse
import subprocess
import sys
import os
from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusDeviceContext
from pymodbus.pdu.device import ModbusDeviceIdentification

# Default Configuration - matches real Alfen hardware
DEFAULT_PORT = 502  # Standard Modbus TCP port
ADDRESS_PRODUCT = 200
ADDRESS_SOCKET_1 = 1
ADDRESS_SOCKET_2 = 2

# Logging setup
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)


def kill_ghost_processes(port):
    """Kill any existing processes listening on the specified port."""
    if sys.platform == 'win32':
        try:
            # Find process using the port
            result = subprocess.run(
                ['powershell', '-Command', 
                 f'Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | '
                 f'Select-Object -ExpandProperty OwningProcess'],
                capture_output=True, text=True, timeout=5
            )
            pids = [pid.strip() for pid in result.stdout.strip().split('\n') if pid.strip()]
            
            current_pid = os.getpid()
            for pid in pids:
                try:
                    pid_int = int(pid)
                    if pid_int != current_pid:
                        log.warning(f"Killing ghost process {pid_int} on port {port}")
                        subprocess.run(['taskkill', '/F', '/PID', str(pid_int)], 
                                      capture_output=True, timeout=5)
                except (ValueError, subprocess.TimeoutExpired):
                    pass
                    
            if pids:
                import time
                time.sleep(1)  # Wait for port to be released
                
        except Exception as e:
            log.debug(f"Ghost process check failed (non-critical): {e}")
    else:
        # Linux/Mac: use lsof
        try:
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True, text=True, timeout=5
            )
            pids = [pid.strip() for pid in result.stdout.strip().split('\n') if pid.strip()]
            
            current_pid = os.getpid()
            for pid in pids:
                try:
                    pid_int = int(pid)
                    if pid_int != current_pid:
                        log.warning(f"Killing ghost process {pid_int} on port {port}")
                        os.kill(pid_int, 9)
                except (ValueError, OSError):
                    pass
                    
            if pids:
                import time
                time.sleep(1)
                
        except Exception as e:
            log.debug(f"Ghost process check failed (non-critical): {e}")

# ============================================================================
# Encoding utilities
# ============================================================================

def to_registers(data_bytes):
    """Converts bytes to a list of 16-bit registers (Big Endian)."""
    if len(data_bytes) % 2 != 0:
        data_bytes += b'\x00'
    return [int.from_bytes(data_bytes[i:i+2], 'big') for i in range(0, len(data_bytes), 2)]

def encode_string(s, length):
    """Encodes a string into registers (null-padded)."""
    s = s[:length].encode('utf-8')
    s += b'\x00' * (length - len(s))
    return to_registers(s)

def encode_float(value):
    """Encodes a float32 into 2 registers (Big Endian)."""
    return to_registers(struct.pack('>f', float(value)))
    
def encode_double(value):
    """Encodes a float64 into 4 registers (Big Endian)."""
    return to_registers(struct.pack('>d', float(value)))

def encode_uint16(value):
    """Encodes a uint16 into 1 register."""
    return [int(value) & 0xFFFF]

def encode_int16(value):
    """Encodes an int16 into 1 register."""
    return [int(value) & 0xFFFF]

def encode_uint32(value):
    """Encodes a uint32 into 2 registers (Big Endian)."""
    return to_registers(struct.pack('>I', int(value)))

def encode_uint64(value):
    """Encodes a uint64 into 4 registers (Big Endian)."""
    return to_registers(struct.pack('>Q', int(value)))

# Helper to set register with offset correction
# Client reads register N, context adds +1 → reads block[N+1]
# So we store at block[N+1] for client to read register N
def reg(register):
    """Convert Modbus register address to block index."""
    return register + 1

# ============================================================================
# Product/Station Context (Unit 200)
# ============================================================================

def setup_product_context():
    """Sets up the product/station context (Unit 200)."""
    block = ModbusSequentialDataBlock(0, [0]*2000)
    
    # === Product Identification (Registers 100-178) ===
    block.setValues(reg(100), encode_string("Alfen Eve Single Pro-line", 34))  # Name (17 regs)
    block.setValues(reg(117), encode_string("Alfen B.V.", 10))  # Manufacturer (5 regs)
    block.setValues(reg(122), encode_uint16(3))  # Modbus Table Version
    block.setValues(reg(123), encode_string("5.16.0-4095", 34))  # Firmware (17 regs)
    block.setValues(reg(140), encode_string("NG920-60559", 34))  # Platform (17 regs)
    block.setValues(reg(157), encode_string("ACE0108752", 22))   # Serial (11 regs)
    
    # Time registers (168-178)
    import datetime
    now = datetime.datetime.now()
    block.setValues(reg(168), encode_int16(now.year))
    block.setValues(reg(169), encode_int16(now.month))
    block.setValues(reg(170), encode_int16(now.day))
    block.setValues(reg(171), encode_int16(now.hour))
    block.setValues(reg(172), encode_int16(now.minute))
    block.setValues(reg(173), encode_int16(now.second))
    block.setValues(reg(174), encode_uint64(3600000))  # Uptime 1 hour in ms
    block.setValues(reg(178), encode_int16(60))  # UTC offset in minutes
    
    # === Station Status (Registers 1100-1105) ===
    block.setValues(reg(1100), encode_float(32.0))   # Station Active Max Current
    block.setValues(reg(1102), encode_float(42.5))   # Temperature
    block.setValues(reg(1104), encode_uint16(1))     # Backoffice Connected
    block.setValues(reg(1105), encode_uint16(1))     # Number of Sockets

    return ModbusDeviceContext(hr=block)

# ============================================================================
# Socket Context (Unit 1 or 2)
# ============================================================================

def setup_socket_context(socket_id):
    """Sets up a socket context (Unit 1 or 2)."""
    block = ModbusSequentialDataBlock(0, [0]*2000)
    
    # === Meter Measurements (Registers 300-424) ===
    # HA reads registers 300-424 (125 registers) and uses offsets from 300
    block.setValues(reg(300), encode_uint16(3))      # Meter State (offset 0)
    block.setValues(reg(301), encode_uint32(1500))   # Meter Age ms (offset 1, 4 regs but read as UINT16)
    block.setValues(reg(305), encode_uint16(1))      # Meter Type (offset 5)
    
    # Voltages L-N (float32, V) - offset 6, 8, 10
    block.setValues(reg(306), encode_float(232.5))   # V L1-N
    block.setValues(reg(308), encode_float(231.8))   # V L2-N
    block.setValues(reg(310), encode_float(233.2))   # V L3-N
    
    # Voltages L-L (float32, V) - offset 12, 14, 16
    block.setValues(reg(312), encode_float(401.2))   # V L1-L2
    block.setValues(reg(314), encode_float(400.8))   # V L2-L3
    block.setValues(reg(316), encode_float(402.1))   # V L3-L1
    
    # Currents (float32, A) - offset 18, 20, 22, 24, 26
    block.setValues(reg(318), encode_float(0.12))    # I Neutral
    block.setValues(reg(320), encode_float(10.2))    # I L1
    block.setValues(reg(322), encode_float(10.1))    # I L2
    block.setValues(reg(324), encode_float(10.3))    # I L3
    block.setValues(reg(326), encode_float(30.6))    # I Sum
    
    # Power Factors (float32, cos φ) - offset 28, 30, 32, 34
    block.setValues(reg(328), encode_float(0.98))    # PF L1
    block.setValues(reg(330), encode_float(0.97))    # PF L2
    block.setValues(reg(332), encode_float(0.98))    # PF L3
    block.setValues(reg(334), encode_float(0.98))    # PF Sum
    
    # Frequency (float32, Hz) - offset 36
    block.setValues(reg(336), encode_float(50.02))
    
    # Real Power (float32, W) - offset 38, 40, 42, 44
    block.setValues(reg(338), encode_float(2325.0))  # P L1
    block.setValues(reg(340), encode_float(2298.0))  # P L2
    block.setValues(reg(342), encode_float(2356.0))  # P L3
    block.setValues(reg(344), encode_float(6979.0))  # P Sum
    
    # Apparent Power (float32, VA) - offset 46, 48, 50, 52
    block.setValues(reg(346), encode_float(2372.0))
    block.setValues(reg(348), encode_float(2348.0))
    block.setValues(reg(350), encode_float(2404.0))
    block.setValues(reg(352), encode_float(7124.0))
    
    # Reactive Power (float32, VAr) - offset 54, 56, 58, 60
    block.setValues(reg(354), encode_float(465.0))
    block.setValues(reg(356), encode_float(502.0))
    block.setValues(reg(358), encode_float(454.0))
    block.setValues(reg(360), encode_float(1421.0))
    
    # Real Energy Delivered (float64, Wh) - offset 62, 66, 70, 74
    block.setValues(reg(362), encode_double(15234.67))  # E L1
    block.setValues(reg(366), encode_double(15198.42))  # E L2
    block.setValues(reg(370), encode_double(15312.89))  # E L3
    block.setValues(reg(374), encode_double(45745.98))  # E Sum
    
    # Real Energy Consumed (float64, Wh) - offset 78, 82, 86, 90
    block.setValues(reg(378), encode_double(0.0))
    block.setValues(reg(382), encode_double(0.0))
    block.setValues(reg(386), encode_double(0.0))
    block.setValues(reg(390), encode_double(0.0))
    
    # Apparent Energy (float64, VAh) - offset 92, 96, 100, 104
    block.setValues(reg(392), encode_double(15542.0))
    block.setValues(reg(396), encode_double(15485.0))
    block.setValues(reg(400), encode_double(15612.0))
    block.setValues(reg(404), encode_double(46639.0))
    
    # Reactive Energy (float64, VArh) - offset 108, 112, 116, 120
    block.setValues(reg(408), encode_double(3024.0))
    block.setValues(reg(412), encode_double(3189.0))
    block.setValues(reg(416), encode_double(2956.0))
    block.setValues(reg(420), encode_double(9169.0))  # Reactive Energy Sum
    
    # === Socket Status/Control (Registers 1200-1215) ===
    # HA reads registers 1200-1215 (16 registers)
    block.setValues(reg(1200), encode_uint16(1))     # Availability (offset 0)
    block.setValues(reg(1201), encode_string("C2", 10))  # Mode 3 State (offset 1, 5 regs)
    block.setValues(reg(1206), encode_float(16.0))   # Actual Applied Max Current (offset 6)
    block.setValues(reg(1208), encode_uint32(60))    # Max Current Valid Time (offset 8)
    block.setValues(reg(1210), encode_float(16.0))   # Modbus Slave Max Current (offset 10)
    block.setValues(reg(1212), encode_float(6.0))    # Active LB Safe Current (offset 12)
    block.setValues(reg(1214), encode_uint16(1))     # Setpoint Accounted (offset 14)
    block.setValues(reg(1215), encode_uint16(3))     # Charging Mode Phases (offset 15)

    return ModbusDeviceContext(hr=block)

# ============================================================================
# Simulation Logic
# ============================================================================

async def update_simulation(context):
    """Updates simulation state periodically.
    
    Mirrors written Max Current (1210) to Actual Applied Max Current (1206).
    """
    while True:
        await asyncio.sleep(1)
        
        for unit in [ADDRESS_SOCKET_1, ADDRESS_SOCKET_2]:
            try:
                slave = context[unit]
                # Read Modbus Slave Max Current (register 1210)
                # Context adds +1, so read from internal address 1211
                values = slave.getValues(3, 1210, 2)
                if isinstance(values, list) and len(values) == 2:
                    # Write to Actual Applied Max Current (register 1206)
                    slave.setValues(3, 1206, values)
            except Exception:
                pass

# ============================================================================
# Main
# ============================================================================

async def run_server(port):
    """Starts the Modbus TCP server."""
    # Kill any ghost processes holding the port
    kill_ghost_processes(port)
    
    store = ModbusServerContext(devices={
        ADDRESS_PRODUCT: setup_product_context(),
        ADDRESS_SOCKET_1: setup_socket_context(1),
        ADDRESS_SOCKET_2: setup_socket_context(2)
    }, single=False)

    identity = ModbusDeviceIdentification()
    identity.VendorName = 'Alfen B.V.'
    identity.ProductCode = 'ACE'
    identity.VendorUrl = 'https://alfen.com'
    identity.ProductName = 'Eve Single Pro-line Simulator'
    identity.ModelName = 'NG920'
    identity.MajorMinorRevision = '5.16.0'

    log.info(f"Starting Alfen Eve Simulator on port {port}...")
    log.info(f"  Unit 200: Product/Station information")
    log.info(f"  Unit 1: Socket 1")
    log.info(f"  Unit 2: Socket 2")
    
    server_task = asyncio.create_task(StartAsyncTcpServer(
        context=store,
        identity=identity,
        address=("0.0.0.0", port)
    ))
    
    simulator_logic = asyncio.create_task(update_simulation(store))
    
    await asyncio.gather(server_task, simulator_logic)

def main():
    parser = argparse.ArgumentParser(description='Alfen Eve Single Pro Modbus Simulator')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_PORT,
                        help=f'TCP port to listen on (default: {DEFAULT_PORT})')
    args = parser.parse_args()
    
    asyncio.run(run_server(args.port))

if __name__ == "__main__":
    main()
