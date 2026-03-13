import socket
import threading


class Server:


    """
    Three TCP servers each running in their own thread:
      Port 8000 — READ  (authoritative DNS lookups)
      Port 9000 — WRITE (write replication)
      Port 7001 — SYNC  (raft heartbeats)

    READ protocol:
      "yahoo.com\n"        — request from control plane (fan out if needed)
      "PEER:yahoo.com\n"   — request from another data plane node (local lookup only)
    """



    def __init__(self, recordReader, _writer, _states, _raft):
        self._recordReader = recordReader
        self._writer       = _writer
        self._states       = _states
        self._raft         = _raft

    def start(self):
        threading.Thread(target=self._serve, args=(8000, self.handle_read),  daemon=False, name="read-server").start()
        threading.Thread(target=self._serve, args=(9000, self.handle_write), daemon=False, name="write-server").start()
        threading.Thread(target=self._serve, args=(7001, self.handle_sync),  daemon=False, name="sync-server").start()

        print("Listening on 8000 (READ)")
        print("Listening on 9000 (WRITE)")
        print("Listening on 7001 (SYNC)")

        threading.Event().wait()

    def _serve(self, port, handler):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("0.0.0.0", port))
        server_sock.listen(50)
        while True:
            try:
                conn, addr = server_sock.accept()
                print(f'got incoming conn from {addr} and socket is {conn}')
                threading.Thread(target=handler, args=(conn, addr), daemon=True).start()
            except Exception as e:
                print(f"[SERVER] Accept error on port {port}: {e}")

    # ------------------------------------------------------------------
    # READ (port 8000)
    # ------------------------------------------------------------------

    def handle_read(self, conn, addr):
        print('inside read handle')
        try:
            f = conn.makefile('r')
            while True:
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    conn.sendall(b"N/A\n")
                    continue

                # PEER: prefix means this came from another node — local lookup only
                if line.startswith("PEER:"):
                    domain = line[5:]
                    record = self._local_lookup(domain)
                    print(f"[READ] peer lookup '{domain}' → {record}")
                else:
                    domain = line
                    print(f"[READ] client request for '{domain}' from {addr}")
                    record = self._resolve(domain)

                conn.sendall((record + '\n').encode())
        except Exception as e:
            print(f"[READ ERROR] {addr}: {e}")
        finally:
            conn.close()

    def _local_lookup(self, domain):
        print('inside local lookup')
        """Only check this node's own shard — no fanout."""
        if domain and domain[0].lower() in self._states.selfRecords:
            return self._recordReader.recordResponse(domain, "A")
        return 'N/A'

    def _resolve(self, domain):
        # Try local shard first
        print('resolve start')
        record = self._local_lookup(domain)
        if record != 'N/A':
            return record

        # Not found locally — forward to leader (or fan out if we are leader)
        if self._raft.leader:
            record = self._raft.sendRead(domain)
            if record != 'N/A':
                return record
            # Still not found — resolve via live DNS and write
            return self._writer.newRecord(domain)
        print('resolve end')
        # Follower: forward to leader
        return self._forward_to_leader(domain)

    def _forward_to_leader(self, domain):
        print('forward to leader start')
        try:
            s = socket.socket()
            s.settimeout(5)
            s.connect((self._states.leaderIp, 8000))
            s.sendall((domain + '\n').encode())
            response = s.makefile('r').readline().strip()
            s.close()
            print(f"[READ] Forwarded '{domain}' to leader → {response}")
            return response if response else 'N/A'
        except Exception as e:
            print(f"[READ] Forward to leader failed: {e}")
            return 'N/A'

    # ------------------------------------------------------------------
    # WRITE (port 9000)
    # ------------------------------------------------------------------

    def handle_write(self, conn, addr):
        try:
            f = conn.makefile('r')
            while True:
                line = f.readline()
                if not line:
                    break
                query = line.strip()
                if not query:
                    continue
                print(f"[WRITE RECV] {query}")
                self._writer.writeHandler(query, self._raft)
                conn.sendall(b"OK\n")
        except Exception as e:
            print(f"[WRITE ERROR] {addr}: {e}")
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # SYNC (port 7001)
    # ------------------------------------------------------------------

    def handle_sync(self, conn, addr):
        try:
            f = conn.makefile('r')
            while True:
                line = f.readline()
                if not line:
                    break
                msg = line.strip()
                if not msg:
                    continue
                self._raft.beatHandler(msg)
                conn.sendall(b"OK\n")
        except Exception as e:
            print(f"[SYNC ERROR] {addr}: {e}")
        finally:
            conn.close()