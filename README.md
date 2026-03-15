# Distributed DNS Service

A distributed DNS service split into a Java control plane and a Python data plane.

---

## How it works

The control plane is a Java/Spring Boot app that receives DNS queries over UDP and TCP. It checks two cache layers before hitting the data plane. The data plane is 3 Python nodes that store the actual DNS records, sharded by the first letter of the domain name. The nodes run Raft for leader election and log replication.

```
DNS client (dig)
      |
      | UDP/TCP port 5354
      |
Control Plane (Java, your Mac)
  - checks L1 cache (port 8100)
  - checks L2 cache (port 8200)
  - if miss, asks data plane (port 8000)
      |
      | TCP port 8000
      |
Data Plane node1 (Docker, port mapped to Mac)
  - if it owns the shard, returns the record
  - if not, fans out to node2/node3 with PEER: prefix
  - if not found anywhere, resolves via live DNS and writes it back
      |
      | internal Docker network (172.18.0.x)
      |
node2, node3 (Docker, internal only)
  - receive PEER: requests from node1
  - do local shard lookup only, no fanout
  - talk to each other on ports 9000 (write) and 7001 (sync)
```

---

## Ports

| what | port | where |
|---|---|---|
| DNS listener | 5354 | your Mac |
| L1 cache | 8100 | Docker, mapped to Mac |
| L2 cache | 8200 | Docker, mapped to Mac |
| data plane READ | 8000 | Docker, mapped to Mac (node1 only) |
| data plane WRITE | 9000 | Docker, mapped to Mac (node1 only) |
| data plane SYNC | 7001 | Docker, mapped to Mac (node1 only) |

node2 and node3 are only reachable inside Docker on the internal network. Only node1 is port-mapped to your Mac.

---

## Files that matter

```
ds-dns/
  docker_compose.yml       -- starts node1/2/3 + l1cache + l2cache + cleaner
  lServers.txt             -- cache server IPs (must be 127.0.0.1 for local)
  states.txt               -- written by data plane on startup, read by Java
  nodes.txt                -- written by data plane, one IP per line
  records/                 -- a.txt through z.txt, 740k+ DNS records
  caches/
    l1_cache.py
    l2_cache.py
  data_plane/
    main.py
    state.py               -- node discovery, shard assignment
    server.py              -- 3 TCP servers (read/write/sync)
    raft/_raft.py          -- leader election, log replication
    read/_read.py          -- local shard lookup
    write/_writer.py       -- raft write pipeline
    batch/_batch.py        -- loads records into memory on startup
  dns-control-plane/
    src/...                -- Java source
    zone.txt               -- cache server IPs for Java (same as lServers.txt)
    target/dns-control-plane-1.0.0.jar
```

---

## How to run

### every time you restart

step 1 - start Docker Desktop, wait for whale icon to stop animating

step 2 - start the data plane and caches

```bash
cd ds-dns
docker compose -f docker_compose.yml down
docker compose -f docker_compose.yml up
```

wait until you see all three nodes print their shards:
```
node1: rank 1/3 shards [a b c d e f g h i]
node2: rank 2/3 shards [j k l m n o p q r]
node3: rank 3/3 shards [s t u v w x y z]
```

step 3 - start the Java control plane in a new terminal

```bash
cd ds-dns/dns-control-plane
mvn spring-boot:run
```

step 4 - test

```bash
dig @127.0.0.1 -p 5354 google.com
dig @127.0.0.1 -p 5354 amazon.com
dig @127.0.0.1 -p 5354 +tcp netflix.com
```

---

## lServers.txt

must always have 127.0.0.1 since caches are port-mapped to your Mac:

```json
{
  "l1Servers": ["127.0.0.1"],
  "l2Servers": ["127.0.0.1"]
}
```

---

## How nodes discover each other

the cleaner container deletes all self_ip_*.txt files first. then each node writes its own IP to a unique file (self_ip_node1.txt etc). state.py waits 4 seconds then reads all those files to build the cluster. this avoids race conditions.

---

## Read request flow

1. Java sends domain to 127.0.0.1:8000
2. node1 receives it (no PEER: prefix = came from outside)
3. node1 checks its own shard first
4. if found, returns it
5. if not found and node1 is leader, sends PEER:domain to node2 and node3
6. node2/node3 do local shard lookup only (PEER: prefix = no fanout)
7. if still not found, node1 resolves via live DNS and writes it back via Raft
8. if node1 is a follower, it forwards the request to the leader

---

## Write flow (Raft)

1. control plane or batch sends type-1 message to port 9000
2. leader increments log number, stores update, replicates to followers (type-2)
3. followers ack (type-3)
4. leader commits — writes to records file and in-memory dict

---

## Cache protocol

```
GET;domain.com     -> ip address        (hit)
                   -> N/A               (miss, L1)
                   -> LEASE;GRANTED     (miss, L2 - go fetch from data plane)
                   -> LEASE;WAITING     (miss, L2 - someone else is fetching)
SET;domain.com;ip  -> OK
```

---

## Raft heartbeat format

sent on port 7001 every 5 seconds:
```
leaderIp;rank;lastRank
```
node with highest IP wins. followers that stop hearing heartbeats for 15 seconds promote themselves.

---

## Record file format

```
amazon.com,A,205.251.242.103
apple.com,A,17.253.144.10
```

files are in records/ named by first letter: a.txt, b.txt ... z.txt, 0.txt ... 9.txt

---

## Common problems

port already in use
```bash
lsof -i :8000 -i :8100 -i :8200 -i :9000 -i :7001
kill -9 <PID>
```

nodes showing wrong rank (e.g. rank 4/6 instead of 1/3)
- stale self_ip_*.txt files from previous run
- the cleaner container handles this automatically now
- if still happening: docker compose down, then up again

Docker daemon not running
- open Docker Desktop and wait for whale to stop animating

PATH broken (mvn/docker not found)
```bash
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin"
```

Java can't reach data plane (Read timed out)
- make sure no other Python process is holding port 8000: lsof -i :8000
- make sure Docker is up and node1 shows "Listening on 8000"