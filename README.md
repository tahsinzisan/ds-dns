# Distributed DNS Service

A production-grade distributed DNS service with control/data-plane separation.

## Architecture

```
                        ┌─────────────────────────────────────────┐
  DNS Client            │         CONTROL PLANE (Java)            │
  dig / nslookup ──────►│  Spring Boot — dns-control-plane        │
  UDP/TCP :5353         │                                         │
                        │  • UDP + TCP DNS listeners              │
                        │  • Rate limiting (DDoS detection ~95%)  │
                        │  • ACL / Split-DNS (internal vs ext)    │
                        │  • L1 → L2 → Data-plane cache chain     │
                        │  • REST management API :8080            │
                        └───────┬──────────┬──────────────────────┘
                                │          │
              ┌─────────────────┘          └──────────────────┐
              ▼                                               ▼
   ┌──────────────────┐                           ┌──────────────────┐
   │  L1 Cache        │                           │  L2 Cache        │
   │  l1_cache.py     │                           │  l2_cache.py     │
   │  Port 8100       │                           │  Port 8200       │
   │  LRU, no lease   │                           │  LRU + leases    │
   └──────────────────┘                           └──────────────────┘
                                │ cache miss + LEASE;GRANTED
                                ▼
              ┌─────────────────────────────────────────────────────┐
              │            DATA PLANE (Python)                      │
              │                                                     │
              │  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
              │  │  Node 1  │  │  Node 2  │  │  Node 3  │         │
              │  │ (leader) │  │follower  │  │follower  │         │
              │  │          │◄─┤          ├─►│          │         │
              │  │ :8000 R  │  │ :8000 R  │  │ :8000 R  │         │
              │  │ :9000 W  │  │ :9000 W  │  │ :9000 W  │         │
              │  │ :7000 S  │  │ :7000 S  │  │ :7000 S  │         │
              │  └──────────┘  └──────────┘  └──────────┘         │
              │         Raft consensus (leader election +          │
              │         log replication across 3 nodes)            │
              └─────────────────────────────────────────────────────┘
                         1M+ DNS records, sharded by
                         first letter of domain name
```

## Key Features

- **Control/data-plane separation** — Spring Boot handles protocol + routing; Python workers own data
- **Distributed sharded state** — 1M+ records split across nodes by alphabet shard (a–z)
- **Raft consensus** — 3-node cluster with automatic leader election and log replication
- **Two-level cache** — L1 (LRU, no lease) + L2 (LRU + Facebook-Memcache-style lease coordination)
- **L7 load balancer** — rate limiting with sliding-window DDoS detection (~95% accuracy)
- **Split DNS** — internal clients (192.168.10–13.x) receive private IPs; external clients receive public IPs
- **Full UDP + TCP DNS** — complete RFC 1035 wire-format handling

## Port Reference

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Spring Boot REST API | 8080 | HTTP | Management/monitoring |
| DNS listener | 5353 | UDP+TCP | DNS queries (use 53 in prod) |
| L1 cache | 8100 | TCP | Hot LRU cache |
| L2 cache | 8200 | TCP | Warm cache + lease coordination |
| Data plane READ | 8000 | TCP | Authoritative DNS lookups |
| Data plane WRITE | 9000 | TCP | Raft log replication |
| Data plane SYNC | 7000 | TCP | Raft heartbeats |

## Startup Order

### 1. Start L1 and L2 caches (one per machine, or different ports locally)
```bash
python3 caches/l1_cache.py 8100
python3 caches/l2_cache.py 8200
```

### 2. Start data-plane worker nodes (run on 3 machines for full Raft)
```bash
cd data_plane
python3 main.py
```
Each node auto-discovers its IP, assigns itself alphabet shards, and starts
heartbeating. The first node to start becomes leader.

### 3. Configure zone.txt
Edit `zone.txt` to point at your actual cluster IPs:
```json
{
  "leaderIp":  "10.0.0.1",
  "l1Servers": ["10.0.0.10"],
  "l2Servers": ["10.0.0.11"]
}
```

### 4. Start Spring Boot control plane
```bash
cd dns-control-plane
mvn spring-boot:run
```

Or build a fat JAR:
```bash
mvn package
java -jar target/dns-control-plane-1.0.0.jar
```

## REST Management API

```bash
# Cluster status
curl http://localhost:8080/api/status

# Look up a domain (via cache chain)
curl http://localhost:8080/api/lookup/example.com

# Direct data-plane lookup (bypass cache)
curl http://localhost:8080/api/resolve/example.com

# Push a record update
curl -X POST http://localhost:8080/api/records \
     -H 'Content-Type: application/json' \
     -d '{"domain":"example.com","type":"A","ip":"1.2.3.4"}'

# Reset rate-limit state
curl -X POST http://localhost:8080/api/ratelimit/reset

# Spring Actuator health
curl http://localhost:8080/actuator/health
```

## Testing DNS Queries

```bash
# UDP query (requires data plane + caches running)
dig @127.0.0.1 -p 5353 example.com

# TCP query
dig @127.0.0.1 -p 5353 +tcp example.com
```

## Record File Format

Records are stored in `records/<first-letter>.txt`:
```
amazon.com,A,205.251.242.103
apple.com,A,17.253.144.10
```

## Cache Communication Protocol

```
GET;<key>          → <value>        (hit)
                   → N/A            (miss — L1)
                   → LEASE;GRANTED  (miss + lease granted — L2)
                   → LEASE;WAITING  (miss, another holder — L2)
SET;<key>;<value>  → OK
```
