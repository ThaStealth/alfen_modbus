import asyncio
from pymodbus.client import AsyncModbusTcpClient

async def debug_read():
    client = AsyncModbusTcpClient("127.0.0.1", port=5020)
    await client.connect()
    
    if not client.connected:
        print("Failed to connect")
        return
    
    # Test reading around register 100 to find where data actually is
    for addr in range(99, 103):
        rr = await client.read_holding_registers(addr, count=2, device_id=200)
        if rr.isError():
            print(f"Reg {addr}: ERROR")
        else:
            # Show as hex and as ASCII
            hex_vals = [hex(x) for x in rr.registers]
            bytes_val = b''.join(r.to_bytes(2, 'big') for r in rr.registers)
            print(f"Reg {addr}: {hex_vals} = {bytes_val}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(debug_read())
