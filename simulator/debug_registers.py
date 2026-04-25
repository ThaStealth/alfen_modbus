"""Debug script to dump raw register values and find actual data locations."""
import asyncio
import struct
import argparse
from pymodbus.client import AsyncModbusTcpClient

async def debug_registers(port):
    client = AsyncModbusTcpClient("127.0.0.1", port=port)
    await client.connect()
    
    if not client.connected:
        print("Failed to connect!")
        return
    
    def decode_float32(regs):
        b = b''.join(r.to_bytes(2, 'big') for r in regs)
        return struct.unpack('>f', b)[0]
    
    print(f"\n=== Unit 1 Socket: Scanning registers 300-330 for voltage data ===")
    print("Looking for voltage values around 230V...")
    
    for base in range(300, 330, 2):
        rr = await client.read_holding_registers(base, count=2, device_id=1)
        if not rr.isError():
            val = decode_float32(rr.registers)
            marker = " <-- VOLTAGE!" if 220 < val < 260 else ""
            marker = " <-- LINE VOLTAGE!" if 380 < val < 420 else marker
            print(f"  Reg {base}: {val:.2f}{marker}")
    
    print(f"\n=== Unit 1 Socket: Scanning registers 1200-1220 for status data ===")
    rr = await client.read_holding_registers(1200, count=20, device_id=1)
    if not rr.isError():
        for i, val in enumerate(rr.registers):
            print(f"  Reg {1200+i}: {val} (0x{val:04x})")
    
    print(f"\n=== Unit 200 Product: Scanning registers 1100-1110 for station data ===")
    rr = await client.read_holding_registers(1100, count=10, device_id=200)
    if not rr.isError():
        for i in range(0, len(rr.registers), 2):
            if i+1 < len(rr.registers):
                val = decode_float32(rr.registers[i:i+2])
                print(f"  Reg {1100+i}: {val:.2f}")
    
    client.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=502)
    args = parser.parse_args()
    asyncio.run(debug_registers(args.port))

if __name__ == "__main__":
    main()
