import asyncio
import websockets

connected_users = set()

async def handle_connection(websocket):
    connected_users.add(websocket)
    try:
        async for message in websocket:
            for user in connected_users:
                if user != websocket:  
                    await user.send(message)
    finally:
        connected_users.remove(websocket)

        
async def start_server(ip_address):
    async with websockets.serve(handle_connection, ip_address, 8765):
        print(f"Server started on ws://{ip_address}:8765")
        await asyncio.Future() 

if __name__ == "__main__":
    ip_address = input("ایپی سرور خود را وارد کنید (مثلاً 127.0.0.1): ")
    asyncio.run(start_server(ip_address))