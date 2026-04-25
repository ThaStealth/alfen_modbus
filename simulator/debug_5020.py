"""Debug script to test the actual simulator on port 5020"""
import asyncio
from pymodbus.client import AsyncModbusTcpClient

PORT = 5020
HOST = "127.0.0.1"

async def run():
    client = AsyncModbusTcpClient(HOST, port=PORT)
    await client.connect()
    
    if not client.connected:
        print("Failed to connect!")
        return
    
    print("Testing actual simulator on port 5020:")
    print("\nUnit 200 (Product) - Name should be at register 100:")
    for addr in range(98, 105):
        rr = await client.read_holding_registers(addr, count=2, device_id=200)
        if rr.isError():
            print(f"  Register {addr}: ERROR {rr}")
        else:
            bytes_val = b''.join(r.to_bytes(2, 'big') for r in rr.registers)
            print(f"  Register {addr}: {bytes_val}")
    
    print("\nUnit 1 (Socket) - Voltage should be at register 306:")
    for addr in range(304, 312):
        rr = await client.read_holding_registers(addr, count=2, device_id=1)
        if rr.isError():
            print(f"  Register {addr}: ERROR {rr}")
        else:
            import struct
            b = b''.join(r.to_bytes(2, 'big') for r in rr.registers)
            try:
                val = struct.unpack('>f', b)[0]
                print(f"  Register {addr}: {val:.2f}")
            except:
                print(f"  Register {addr}: {b.hex()}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(run())
