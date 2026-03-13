"""
Control Plane record-refresh process.

Reads the current cluster state from states.txt to discover:
  - Which record shards belong to this node (selfRecords)
  - The current leader's IP (leaderIp)

For each record in the node's shards, resolves the domain name and, if the
live IP differs from the stored record, pushes an update to the data-plane
leader via the Raft write server (port 9000).

FIX: Originally sent updates to port 7000 (Raft heartbeat/sync server).
     Corrected to port 9000 (Raft write server) with the proper type-1
     message format: "1;<domain>,<record_type>,<ip>\n"
"""

import json
import socket
import os


def send_update(domain, ip, leader_ip):
    """
    Push a DNS record update to the data-plane leader's write server.

    Message format: "1;<domain>,A,<ip>\n"
    Type 1 = new write initiated by control plane (triggers Raft replication).
    """
    update = f'1;{domain},A,{ip}'
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((leader_ip, 9000))   # FIX: port 9000 (write server), was 7000
        s.sendall((update + '\n').encode())
        s.close()
        print(f'[PROCESS] Updated {domain} -> {ip} (sent to leader {leader_ip}:9000)')
    except Exception as e:
        print(f'[PROCESS] Failed to send update for {domain}: {e}')


def main():
    states_path = os.path.join(os.path.dirname(__file__), '..', 'states.txt')

    try:
        with open(states_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print('[PROCESS] states.txt not found — is the data plane running?')
        return
    except json.JSONDecodeError as e:
        print(f'[PROCESS] Failed to parse states.txt: {e}')
        return

    self_records = data.get('selfRecords', [])
    leader_ip    = data.get('leaderIp', '127.0.0.1')
    records_dir  = os.path.join(os.path.dirname(__file__), '..', 'records')

    print(f'[PROCESS] Scanning shards {self_records} — leader: {leader_ip}')

    for head in self_records:
        filepath = os.path.join(records_dir, f'{head}.txt')
        if not os.path.exists(filepath):
            print(f'[PROCESS] Shard file {filepath} not found — skipping')
            continue

        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split(',')
                if len(parts) < 3:
                    continue

                domain, rtype, stored_ip = parts[0].strip(), parts[1].strip(), parts[2].strip()

                try:
                    live_ip = socket.gethostbyname(domain)
                    if live_ip != stored_ip:
                        print(f'[PROCESS] {domain}: stored={stored_ip} live={live_ip} — pushing update')
                        send_update(domain, live_ip, leader_ip)
                except socket.gaierror:
                    # Domain unresolvable from this host — skip
                    continue


if __name__ == '__main__':
    main()
