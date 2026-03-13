package com.dns.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;

/**
 * Cluster topology loaded from zone.txt at startup.
 *
 * zone.txt format (JSON):
 * {
 *   "leaderIp":  "192.168.1.10",
 *   "l1Servers": ["192.168.1.11", "192.168.1.12"],
 *   "l2Servers": ["192.168.1.13", "192.168.1.14"]
 * }
 *
 * leaderIp  - IP of the current Raft leader (authoritative data-plane node)
 * l1Servers - IPs of L1 cache nodes (hot LRU, no lease)
 * l2Servers - IPs of L2 cache nodes (warm LRU, lease-based coordination)
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class ZoneConfig {

    private String leaderIp;
    private List<String> l1Servers;
    private List<String> l2Servers;

    public ZoneConfig() {}

    public ZoneConfig(String leaderIp, List<String> l1Servers, List<String> l2Servers) {
        this.leaderIp  = leaderIp;
        this.l1Servers = l1Servers;
        this.l2Servers = l2Servers;
    }

    public String getLeaderIp()                  { return leaderIp; }
    public void   setLeaderIp(String leaderIp)   { this.leaderIp = leaderIp; }

    public List<String> getL1Servers()                     { return l1Servers; }
    public void         setL1Servers(List<String> servers) { this.l1Servers = servers; }

    public List<String> getL2Servers()                     { return l2Servers; }
    public void         setL2Servers(List<String> servers) { this.l2Servers = servers; }

    @Override
    public String toString() {
        return "ZoneConfig{leaderIp='" + leaderIp
                + "', l1Servers=" + l1Servers
                + ", l2Servers=" + l2Servers + "}";
    }
}
