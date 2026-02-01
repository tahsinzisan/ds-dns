import asyncio
import time

store = {}
leases = {}          # key -> lease_expiry
LEASE_TTL = 0.1      # 100 ms

async def handle_client(reader, writer):
    while True:
        data = await reader.readline()
        if not data:
            break

        cmd = data.decode().strip().split(';')
        now = time.time()

        if cmd[0] == "GET":
            key = cmd[1]
            if key in store:
                writer.write(f"VALUE {store[key]}\n".encode())
            else:
                writer.write(b"MISS\n")

        elif cmd[0] == "LEASE":
            key = cmd[1]
            expiry = leases.get(key, 0)
            if expiry < now:
                leases[key] = now + LEASE_TTL
                writer.write(b"LEASE;GRANTED\n")
            else:
                writer.write(b"LEASE;DENIED\n")

        elif cmd[0] == "SET":
            key, value = cmd[1], cmd[2]
            store[key] = value
            leases.pop(key, None)
            writer.write(b"OK\n")

        await writer.drain()

    writer.close()

async def main():
    server = await asyncio.start_server(handle_client, "127.0.0.1", 6000)
    async with server:
        await server.serve_forever()

asyncio.run(main())
