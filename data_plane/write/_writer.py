from collections import defaultdict
import socket

RED   = "\033[31m"
RESET = "\033[0m"


class Writer:
    """
    Handles the Raft write pipeline for DNS record updates.

    Message types (received on port 9000):
        1;<update>           — new write from control plane (leader only)
        2;<logNum>;<update>  — replicated log entry arriving at a follower
        3;<logNum>           — ack from a follower (leader only)
        4;<logNum>           — commit signal from the leader (follower only)

    <update> format:  domain,record_type,ip_address  (comma-separated)
    """

    def __init__(self, _states):
        self._states = _states
        self.logs   = defaultdict(str)
        self.logAck = defaultdict(int)
        self._raft  = None

    def writeHandler(self, query, _raft):
        self._raft = _raft
        parts = query.strip().split(';')
        msg_type = parts[0]

        if msg_type == '1':
            if len(parts) < 2:
                print(f'[WRITER] Malformed type-1: {query}')
                return
            update = parts[1]
            _raft.currLogNum += 1
            num = str(_raft.currLogNum)
            self.writeStarter(update, num)

        elif msg_type == '2':
            if len(parts) < 3:
                print(f'[WRITER] Malformed type-2: {query}')
                return
            num, update = parts[1], parts[2]
            self.logs[num] = update
            # FIX: was storing 't' (record type) instead of 'ip'
            rec_parts = update.strip().split(',')
            if len(rec_parts) == 3:
                dom, t, ip = rec_parts
                if dom and dom[0].lower() in self._states.selfRecords:
                    self._states.records[(dom.strip(), t.strip())] = ip.strip()
            _raft.sendAck(num)

        elif msg_type == '3':
            if len(parts) < 2:
                return
            self.ackHandler(parts[1])

        elif msg_type == '4':
            if len(parts) < 2:
                return
            self.commitHandler(parts[1])

    def writeStarter(self, update, num):
        self.logs[num] = update
        log_msg = f'{num};{update}'     # FIX: removed '2;' prefix — sendLog adds it
        self._raft.sendLog(log_msg, num)
        self.commitHandler(num)

    def ackHandler(self, num):
        self.logAck[num] += 1
        if self._raft.followerCount > 0 and self.logAck[num] >= self._raft.followerCount:
            print(f'[WRITER] Quorum reached for log #{num}')

    def commitHandler(self, num):
        update = self.logs.get(num)
        if not update:
            print(f'[WRITER] No log entry for num={num}')
            return

        # FIX: update is 'domain,type,ip' (comma-separated) — was wrongly splitting on ';'
        parts = update.strip().split(',')
        if len(parts) < 3:
            print(f'[WRITER] Malformed log entry: {update}')
            return

        domain, rtype, ip = parts[0].strip(), parts[1].strip(), parts[2].strip()
        shard = domain[0].lower()
        filepath = f'../records/{shard}.txt'

        try:
            lines = []
            found = False
            try:
                with open(filepath, 'r') as f:
                    for line in f:
                        if line.strip().split(',')[0].strip() == domain:
                            lines.append(update + '\n')
                            found = True
                        else:
                            lines.append(line)
            except FileNotFoundError:
                pass

            if not found:
                lines.append(update + '\n')

            with open(filepath, 'w') as f:
                f.writelines(lines)

            # Update in-memory records too
            self._states.records[(domain, rtype)] = ip
            print(f'[WRITER] Committed log #{num}: {update}')

        except OSError as e:
            print(f'[WRITER] Failed to write {filepath}: {e}')

    def newRecord(self, domain):
        """Resolve domain via DNS and write it as a new record."""
        try:
            ip = socket.gethostbyname(domain)
            update = f'{domain},A,{ip}'
            self._raft.currLogNum += 1
            num = str(self._raft.currLogNum)
            self.writeStarter(update, num)
            return ip
        except Exception as e:
            print(f"[WRITER] Failed to resolve {RED}{domain}: {e}{RESET}")
        return 'N/A'
