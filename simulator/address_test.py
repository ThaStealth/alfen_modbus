"""Test script to verify exact addressing behavior of pymodbus 3.11.4"""
import asyncio
from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusDeviceContext
from pymodbus.client import AsyncModbusTcpClient

PORT = 5021  # Use different port to avoid conflicts

async def run_test():
    # Create a simple context with known data
    block = ModbusSequentialDataBlock(0, [0]*100)
    # Store value 0xABCD at index 10
    block.setValues(10, [0xABCD])
    # Store value 0x1234 at index 11
    block.setValues(11, [0x1234])
    
    context = ModbusDeviceContext(hr=block)
    store = ModbusServerContext(devices={1: context}, single=False)
    
    # Start server
    server = asyncio.create_task(StartAsyncTcpServer(
        context=store,
        address=("127.0.0.1", PORT)
    ))
    
    await asyncio.sleep(1)  # Wait for server to start
    
    # Connect client
    client = AsyncModbusTcpClient("127.0.0.1", port=PORT)
    await client.connect()
    
    print("Testing address mapping:")
    for addr in range(8, 13):
        rr = await client.read_holding_registers(addr, count=1, device_id=1)
        if rr.isError():
            print(f"  Register {addr}: ERROR")
        else:
            print(f"  Register {addr}: {hex(rr.registers[0])}")
    
    # The key question: which register returns 0xABCD?
    # If block.setValues(10, [0xABCD]) is read at register 9, offset is +1
    # If read at register 10, no offset needed
    
    client.close()
    server.cancel()
    
    print("\nExpected: Register 9 should return 0xABCD if context adds +1")
    print("          Register 10 should return 0xABCD if no offset")

if __name__ == "__main__":
    asyncio.run(run_test())
