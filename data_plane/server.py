# server.py
import asyncio
from raft import Raft


class Server:
    def __init__(self, recordReader, _writer, _states):
        self._recordReader = recordReader
        self._writer = _writer
        self._raft = Raft(_states)

    # ---------- READ SERVER (9000) ----------
    async def handle_read(self, reader, writer):
        addr = writer.get_extra_info("peername")
        print(f"[READ CONNECT] {addr}")

        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                domain = data.decode().rstrip()
                record = self._recordReader.recordResponse(domain, "A")
                if record == 'fd': 
                    self._raft.sendRead(domain)
                writer.write(record.encode())
                await writer.drain()

        except Exception as e:
            print(f"[READ ERROR] {addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"[READ DISCONNECT] {addr}")

    # ---------- WRITE SERVER (8000) ----------
    async def handle_write(self, reader, writer):
        addr = writer.get_extra_info("peername")
        print(f"[WRITE CONNECT] {addr}")

        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                query = data.decode().rstrip()
                print(f"[WRITE RECV] {query}")
                self._writer.writeHandler(query, self._raft)

        except Exception as e:
            print(f"[WRITE ERROR] {addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"[WRITE DISCONNECT] {addr}")

    # ---------- THIRD SERVER (7000) ----------
    async def handle_sync(self, reader, writer):
        addr = writer.get_extra_info("peername")
        print(f"[SYNC CONNECT] {addr}")

        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                msg = data.decode().rstrip()
                print(f"[SYNC RECV] {msg}")
                self._raft.beatHandler(msg)
                # example response
                writer.write(b"OK\n")
                await writer.drain()

        except Exception as e:
            print(f"[SYNC ERROR] {addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"[SYNC DISCONNECT] {addr}")

    # ---------- START ALL SERVERS ----------
    async def start(self):
        read_server = await asyncio.start_server(
            self.handle_read, "0.0.0.0", 8000
        )
        write_server = await asyncio.start_server(
            self.handle_write, "0.0.0.0", 9000
        )
        sync_server = await asyncio.start_server(
            self.handle_sync, "0.0.0.0", 7000 
        )

        print("Listening on 9000 (READ)")
        print("Listening on 8000 (WRITE)")
        print("Listening on 7000 (SYNC)")

        async with read_server, write_server, sync_server:
            await asyncio.gather(
                read_server.serve_forever(),
                write_server.serve_forever(),
                sync_server.serve_forever(),
            )
