import socket
import json
import time
import os

ALPHABET      = 'abcdefghijklmnopqrstuvwxyz'
TOTAL_LETTERS = len(ALPHABET)


class States:

    def __init__(self):
        self.selfRecords = set()
        self.selfIp      = self.get_advertised_ip()
        self.records     = {}

        self._register_and_load_nodes()

        self.leader       = True
        self.beatInterval = 100
        self.leaderDead   = 300
        self.nodeCount    = len(self.nodes)
        self.leaderIp     = self.selfIp
        self.updateRecordSet()
        self.updateState()

    def _register_and_load_nodes(self):
        """
        Each container writes its own IP to a unique file (self_ip_nodeX.txt).
        We wait briefly then collect all self_ip_*.txt files to build nodes.txt.
        This avoids the race condition of multiple containers writing to the same file.
        """
        project_dir = '..'

        # Write own IP to a unique file so other nodes can discover us
        my_file = os.path.join(project_dir, f'self_ip_{self.selfIp.replace(".", "_")}.txt')
        with open(my_file, 'w') as f:
            f.write(self.selfIp + '\n')

        # Wait for sibling containers to write their IPs
        time.sleep(3)

        # Collect all self_ip_*.txt files
        nodes    = {}
        currRank = 0
        ip_files = sorted([
            fn for fn in os.listdir(project_dir)
            if fn.startswith('self_ip_') and fn.endswith('.txt')
        ])

        for fn in ip_files:
            path = os.path.join(project_dir, fn)
            try:
                ip = open(path).read().strip()
                if ip:
                    currRank += 1
                    nodes[ip] = currRank
            except OSError:
                pass

        if not nodes:
            nodes[self.selfIp] = 1
            currRank = 1

        self.nodes     = nodes
        self.rank      = nodes.get(self.selfIp, 1)
        self.lastRank  = currRank
        self.mLastRank = currRank

        # Also write nodes.txt for compatibility with other tools
        with open(os.path.join(project_dir, 'nodes.txt'), 'w') as f:
            for ip in nodes:
                f.write(ip + '\n')

        print(f"[STATE] Cluster nodes: {list(nodes.keys())}")

    def get_advertised_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()

    def setLeaderIp(self, ip):
        self.leaderIp = ip
        self.updateState()

    def addNodes(self, ip):
        if ip in self.nodes:
            return
        self.nodeCount += 1
        self.nodes[ip] = self.nodeCount
        self.lastRank  = len(self.nodes)
        self.updateRecordSet()

    def removeNode(self, ip):
        if ip not in self.nodes:
            return
        del self.nodes[ip]
        self.nodeCount = len(self.nodes)
        for i, node_ip in enumerate(list(self.nodes.keys()), start=1):
            self.nodes[node_ip] = i
        self.rank     = self.nodes.get(self.selfIp, 1)
        self.lastRank = len(self.nodes)
        self.updateRecordSet()

    def updateRank(self, rank, lastRank):
        self.rank     = rank
        self.lastRank = lastRank
        self.updateRecordSet()

    def updateRecordSet(self):
        if self.nodeCount == 1:
            self.selfRecords = set(ALPHABET)
            print(f"[STATE] Single node — owns all 26 shards")
            return

        rank     = self.rank
        lastRank = self.lastRank

        if lastRank == 0 or rank == 0:
            self.selfRecords = set()
            return

        per_node  = TOTAL_LETTERS // lastRank
        remainder = TOTAL_LETTERS % lastRank
        start     = per_node * (rank - 1) + min(rank - 1, remainder)
        size      = per_node + (1 if rank <= remainder else 0)

        self.selfRecords = set(ALPHABET[start:start + size])
        print(f"[STATE] Shard assigned: {sorted(self.selfRecords)} (rank {rank}/{lastRank})")
        self.updateState()

    def to_state_dict(self):
        return {
            "selfIp":       self.selfIp,
            "nodes":        self.nodes,
            "rank":         self.rank,
            "lastRank":     self.lastRank,
            "leader":       self.leader,
            "beatInterval": self.beatInterval,
            "leaderDead":   self.leaderDead,
            "nodeCount":    self.nodeCount,
            "leaderIp":     self.leaderIp,
            "selfRecords":  list(self.selfRecords),
        }

    def updateState(self):
        try:
            with open('../states.txt', 'w') as f:
                json.dump(self.to_state_dict(), f, indent=2)
        except OSError as e:
            print(f"[STATE] Warning: could not write states.txt: {e}")