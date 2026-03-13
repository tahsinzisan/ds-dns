import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from state import States
from read import Reader
from write import Writer
from server import Server
from batch import Batch
from raft import Raft


def main():
    print("[DATA-PLANE] Starting worker node...")
    states = States()
    print(f"[DATA-PLANE] Self IP: {states.selfIp}")
    print(f"[DATA-PLANE] Assigned shards: {sorted(states.selfRecords)}")

    reader = Reader(states)
    writer = Writer(states)
    raft   = Raft(states)
    batch  = Batch(states, raft)
    server = Server(reader, writer, states, raft)

    server.start()   # blocks forever — no asyncio.run() needed


if __name__ == "__main__":
    main()