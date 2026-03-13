"""
L2 Cache — Warm shared cache with lease-based coordination.

Inspired by the Facebook Memcache paper ("Scaling Memcache at Facebook", NSDI 2013).
The lease mechanism prevents the thundering-herd problem: when many clients
simultaneously miss on the same key, only one is granted a lease and fetches
from the data-plane leader; the others wait and then read the populated value.

Protocol (TCP, default port 8200):
    GET;<key>          -> <value>          (cache hit)
                       -> LEASE;GRANTED    (cache miss -- caller must fetch & SET)
                       -> LEASE;WAITING    (another caller holds the lease -- poll)
    SET;<key>;<value>  -> OK               (populates cache, releases any lease)

Lease lifecycle:
  1. First GET on a missing key  -> LEASE;GRANTED  (lease created, 5s TTL)
  2. Subsequent GETs before SET  -> LEASE;WAITING
  3. Holder calls SET            -> value stored, lease released
  4. If lease expires (>5s)      -> next GET becomes new LEASE;GRANTED
"""

import asyncio
import sys
import time
from collections import OrderedDict

LEASE_TTL_SECONDS = 5.0


class LRUCache:
    def __init__(self, capacity=100000):
        self.capacity = capacity
        self.cache = OrderedDict()

    def get(self, key):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def __len__(self):
        return len(self.cache)


CACHE = LRUCache(capacity=100000)
lease_map = {}   # key -> monotonic timestamp of lease grant


def process_command(line):
    if not line:
        return "ERROR"

    upper = line.upper()

    if upper.startswith("GET;"):
        key = line[4:].strip()
        value = CACHE.get(key)
        if value is not None:
            lease_map.pop(key, None)
            return value

        now = time.monotonic()
        lease_issued_at = lease_map.get(key)

        if lease_issued_at is None or (now - lease_issued_at) > LEASE_TTL_SECONDS:
            lease_map[key] = now
            return "LEASE;GRANTED"

        return "LEASE;WAITING"

    if upper.startswith("SET;"):
        parts = line.split(';', 2)
        if len(parts) < 3:
            return "ERROR"
        _, key, value = parts
        CACHE.set(key.strip(), value.strip())
        lease_map.pop(key.strip(), None)
        return "OK"

    return "ERROR"


async def handle_client(reader, writer):
    addr = writer.get_extra_info("peername")
    try:
        while True:
            data = await reader.readline()
            if not data:
                break
            line = data.decode().rstrip()
            response = process_command(line)
            writer.write((response + '\n').encode())
            await writer.drain()
    except Exception as e:
        print(f"[L2] Client {addr} error: {e}")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def main(port=8200):
    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    print(f"[L2-CACHE] Listening on :{port} (capacity={CACHE.capacity}, lease_ttl={LEASE_TTL_SECONDS}s)")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8200
    asyncio.run(main(port))
