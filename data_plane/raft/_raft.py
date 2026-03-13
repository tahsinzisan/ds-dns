import threading
import time
import ipaddress
import socket


class Raft:
    """
    Raft-style leader-election and log-replication coordinator.

    Heartbeat format (port 7001):  <leaderIp>;<rank>;<lastRank>
    Write message types (port 9000):
        1;<update>           - new write from control plane
        2;<logNum>;<update>  - replicated log entry (leader -> follower)
        3;<logNum>           - ack (follower -> leader)
        4;<logNum>           - commit (leader -> follower)
    """

    def __init__(self, _states):
        self._states = _states
        self.currLogNum = 0
        self.followerCount = max(len(_states.nodes) - 1, 0)
        self.leader = True
        self.beatInterval = _states.beatInterval
        self.leaderDead = _states.leaderDead
        self.beatSent = False
        self._last_beat_received = time.monotonic()

        task = threading.Thread(target=self.raftHeart, daemon=True)
        task.start()
        print('[RAFT] Raft coordinator started')

    def beatHandler(self, beat):
        """Process an incoming heartbeat from another node."""
        self._last_beat_received = time.monotonic()

        try:
            parts = beat.strip().split(';')
            if len(parts) < 3:
                print(f"[RAFT] Malformed beat (need 3 parts): '{beat}'")
                return
            leaderIp = parts[0]
            rank     = int(parts[1])
            lastRank = int(parts[2])
        except (ValueError, IndexError) as e:
            print(f"[RAFT] Error parsing beat '{beat}': {e}")
            return

        # Register node if new
        if leaderIp not in self._states.nodes:
            self._states.mLastRank += 1
            self._states.nodes[leaderIp] = self._states.mLastRank
        self.followerCount = max(len(self._states.nodes) - 1, 0)

        try:
            ldIp = ipaddress.IPv4Address(leaderIp)
            myIp = ipaddress.IPv4Address(self._states.leaderIp)
        except ValueError:
            return

        # Higher IP wins leadership
        if ldIp > myIp:
            self.leader = False
            self._states.leaderIp = leaderIp

        # Update shard assignment if changed
        if self._states.rank != rank or self._states.lastRank != lastRank:
            self._states.updateRank(rank, lastRank)

    def raftHeart(self):
        next_beat_time = time.monotonic() + self.beatInterval

        while True:
            time.sleep(1)
            now = time.monotonic()

            if now >= next_beat_time:
                if self.leader:
                    self.sendBeat()
                next_beat_time = now + self._states.beatInterval

            if not self.leader:
                seconds_since_beat = now - self._last_beat_received
                if seconds_since_beat >= self._states.leaderDead:
                    print('[RAFT] Leader timeout — promoting self to leader')
                    self._states.removeNode(self._states.leaderIp)
                    self._states.leaderIp = self._states.selfIp
                    rank = self._states.nodes.get(self._states.selfIp, 1)
                    self._states.updateRank(rank, self._states.lastRank)
                    self.leader = True
                    self.sendBeat()
                    next_beat_time = now + self._states.beatInterval
                    self._last_beat_received = now

    def sendBeat(self):
        """Broadcast heartbeat to all followers."""
        self.beatSent = True
        for ip, rank in list(self._states.nodes.items()):
            if ip == self._states.selfIp:
                continue
            msg = f'{self._states.selfIp};{rank};{self._states.lastRank}\n'
            self._send_raw(ip, 7001, msg)

    def sendLog(self, log, num):
        """
        Replicate a log entry to all followers.
        FIX: log is already 'num;update' from writeStarter.
        We prepend '2;' here to form the full '2;num;update' message.
        Previously writeStarter was also prepending '2;' causing double prefix.
        """
        self.currLogNum = int(num)
        self.sendToFollower(9000, '2;' + log)

    def sendAck(self, num):
        """Send acknowledgement to the leader."""
        if self.leader:
            return
        self._send_raw(self._states.leaderIp, 9000, f'3;{num}\n')

    def sendRead(self, domain):
        """
        On the leader: query all followers for a domain not in this shard.
        Returns the first non-N/A response, or 'N/A' if none found.
        NOTE: this is synchronous — only call from a thread, not from asyncio.
        """
        if not self.leader:
            return 'N/A'
        for ip in list(self._states.nodes.keys()):
            if ip == self._states.selfIp:
                continue
            try:
                s = socket.socket()
                s.settimeout(2)
                s.connect((ip, 8000))
                s.sendall(('PEER:' + domain + '\n').encode())
                response = s.recv(4096).decode().strip()
                s.close()
                if response and response != 'N/A':
                    return response
            except Exception as e:
                print(f'[RAFT] Could not reach {ip}:8000 — {e}')
        return 'N/A'

    def sendToFollower(self, port, msg):
        """Send a message to every non-self node."""
        for ip in list(self._states.nodes.keys()):
            if ip == self._states.selfIp:
                continue
            self._send_raw(ip, port, msg + '\n')

    def _send_raw(self, ip, port, msg):
        """Fire-and-forget TCP send."""
        try:
            s = socket.socket()
            s.settimeout(2)
            s.connect((ip, port))
            s.sendall(msg.encode())
            s.close()
        except Exception as e:
            print(f'[RAFT] Could not reach {ip}:{port} — {e}')