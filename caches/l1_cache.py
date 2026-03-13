"""
L1 Cache — Hot, in-process LRU cache (no lease coordination).

Protocol (TCP, default port 8100):
    GET;<key>          → <value>   |  N/A
    SET;<key>;<value>  → OK

L1 is the innermost cache tier.  It is checked first on every DNS query and
is intentionally small (fast eviction) so it stays hot.  On a miss it simply
returns "N/A"; the caller then falls through to L2.

No lease is issued at L1 — lease coordination only happens at L2.
"""

import asyncio
import sys
from collections import OrderedDict

# ------------------------------------------------------------------
# LRU Cache implementation
# ------------------------------------------------------------------

class LRUCache:
    """Thread-safe LRU cache backed by an OrderedDict."""

    def __init__(self, capacity: int = 10_000):
        self.capacity = capacity
        self.cache: OrderedDict[str, str] = OrderedDict()

    def get(self, key: str) -> str | None:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)     # mark as recently used
        return self.cache[key]

    def set(self, key: str, value: str) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # evict LRU entry

    def __len__(self) -> int:
        return len(self.cache)


# ------------------------------------------------------------------
# Async TCP server
# ------------------------------------------------------------------

CACHE = LRUCache(capacity=50_000)


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
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
        print(f"[L1] Client {addr} error: {e}")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


def process_command(line: str) -> str:
    """
    Parse and execute a single cache command.

    GET;<key>          → value | N/A
    SET;<key>;<value>  → OK    | ERROR
    """
    if not line:
        return "ERROR"

    upper = line.upper()

    if upper.startswith("GET;"):
        key = line[4:].strip()
        value = CACHE.get(key)
        return value if value is not None else "N/A"

    if upper.startswith("SET;"):
        parts = line.split(';', 2)
        if len(parts) < 3:
            return "ERROR"
        _, key, value = parts
        CACHE.set(key.strip(), value.strip())
        return "OK"

    return "ERROR"


async def main(port: int = 8100):
    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    print(f"[L1-CACHE] Listening on :{port} (capacity={CACHE.capacity:,})")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8100
    asyncio.run(main(port))
