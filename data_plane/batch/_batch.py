import threading
import socket

RED   = "\033[31m"
RESET = "\033[0m"


class Batch:
    """
    Background thread that checks every record in this node's shards
    and pushes updates to the write server if the live IP has changed.
    """

    def __init__(self, _states, _raft):
        self._raft   = _raft
        self._states = _states
        task = threading.Thread(target=self.process, daemon=True)
        task.start()

    def process(self):
        return 
        for shard in self._states.selfRecords:
            try:
                with open(f'../records/{shard}.txt', 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        parts = line.split(',')
                        if len(parts) != 3:
                            continue
                        dom, t, ip = parts
                        try:
                            rip = socket.gethostbyname(dom)
                            '''if rip != ip:
                                # FIX: was sending to port 8000 (READ server) — must be 9000 (WRITE)
                                # FIX: added '\n' terminator required by server's readline()
                                print('not match')
                                self._raft._send_raw(
                                    self._states.leaderIp, 9000,
                                    f'1;{dom},{t},{rip}\n'
                                )'''
                        except Exception as e:
                            print(f"[BATCH] Failed to resolve {RED}{dom}: {e}{RESET}")
            except FileNotFoundError:
                print(f"[BATCH] Shard file for '{shard}' not found — skipping")
