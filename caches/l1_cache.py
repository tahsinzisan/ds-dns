import asyncio

store = {}

async def handle_client(reader, writer):
    while True:
        data = await reader.readline()
        if not data:
            break

        cmd = data.decode().strip().split(';')

        if cmd[0] == "GET":
            key = cmd[1]
            if key in store:
                writer.write(f"VALUE {store[key]}\n".encode())
            else:
                writer.write(b"MISS\n")

        elif cmd[0] == "SET":
            key, value = cmd[1], cmd[2]
            store[key] = value
            writer.write(b"OK\n")

        await writer.drain()

    writer.close()

async def main():
    server = await asyncio.start_server(handle_client, "127.0.0.1", 6000)
    async with server:
        await server.serve_forever()

asyncio.run(main())