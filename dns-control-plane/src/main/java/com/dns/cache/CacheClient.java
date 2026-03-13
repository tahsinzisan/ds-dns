package com.dns.cache;

import com.dns.model.ZoneConfig;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.net.Socket;
import java.util.List;

/**
 * Two-level cache client: L1 (8100) → L2 (8200) → data plane (8000).
 *
 * FIXES:
 *  - fetchFromDataPlane returned "0.0.0.0" on miss → now returns ""
 *    so callers send NXDOMAIN instead of a bogus IP
 *  - waitForLease: NullPointerException when r==null before startsWith check
 *  - send() returned "N/A" on error → now returns null so callers handle consistently
 */
@Component
public class CacheClient {

    private static final Logger log = LoggerFactory.getLogger(CacheClient.class);

    private static final long FNV_OFFSET = 0xcbf29ce484222325L;
    private static final long FNV_PRIME  = 0x100000001b3L;

    private static final int SOCKET_TIMEOUT_MS = 50000;
    private static final int LEASE_WAIT_MS     = 100;
    private static final int LEASE_MAX_RETRIES = 30;

    @Autowired
    private ZoneConfig zoneConfig;

    @Value("${dns.cache.l1.port:8100}")
    private int l1Port;

    @Value("${dns.cache.l2.port:8200}")
    private int l2Port;

    @Value("${dns.dataplane.port:8000}")
    private int dataplanePort;

    public String resolve(String domain) {
        log.info("inside cacheclient");
        String l1Ip = selectServer(zoneConfig.getL1Servers(), domain);
        String result = send(l1Ip, l1Port, "GET;" + domain);
        if (isHit(result)) {
            log.debug("[L1 HIT] {} → {}", domain, result);
            return result;
        }

        String l2Ip = selectServer(zoneConfig.getL2Servers(), domain);
        result = send(l2Ip, l2Port, "GET;" + domain);
        if (isHit(result)) {
            log.debug("[L2 HIT] {} → {}", domain, result);
            send(l1Ip, l1Port, "SET;" + domain + ";" + result);
            return result;
        }

        if ("LEASE;GRANTED".equals(result)) {
            String value = fetchFromDataPlane(domain);
            if (value != null && !value.isBlank()) {
                send(l2Ip, l2Port, "SET;" + domain + ";" + value);
                send(l1Ip, l1Port, "SET;" + domain + ";" + value);
            }
            return value != null ? value : "";
        }

        if (result != null && result.startsWith("LEASE;")) {
            return waitForLease(l2Ip, l1Ip, domain);
        }

        // Full cache miss — go straight to data plane
        String value = fetchFromDataPlane(domain);
        if (value != null && !value.isBlank()) {
            send(l2Ip, l2Port, "SET;" + domain + ";" + value);
            send(l1Ip, l1Port, "SET;" + domain + ";" + value);
        }
        return value != null ? value : "";
    }

    private String waitForLease(String l2Ip, String l1Ip, String domain) {
        for (int i = 0; i < LEASE_MAX_RETRIES; i++) {
            try { Thread.sleep(LEASE_WAIT_MS); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); break; }

            String r = send(l2Ip, l2Port, "GET;" + domain);
            if (isHit(r)) {
                send(l1Ip, l1Port, "SET;" + domain + ";" + r);
                return r;
            }
            // FIX: check null BEFORE calling startsWith to avoid NullPointerException
            if (r == null || !r.startsWith("LEASE;")) break;

            if (r.startsWith("LEASE;GRANTED")) {
                String value = fetchFromDataPlane(domain);
                if (value != null && !value.isBlank()) {
                    send(l2Ip, l2Port, "SET;" + domain + ";" + value);
                    send(l1Ip, l1Port, "SET;" + domain + ";" + value);
                }
                return value != null ? value : "";
            }
        }
        return fetchFromDataPlane(domain);
    }

    private String fetchFromDataPlane(String domain) {
        String leaderIp = zoneConfig.getLeaderIp();
        // Data plane read server expects plain domain (no GET; prefix)
        String response = send(leaderIp, dataplanePort, domain);
        // FIX: was returning "0.0.0.0" on miss → now returns "" so caller sends NXDOMAIN
        if (response == null || response.isBlank() || "N/A".equals(response)) return "";
        return response;
    }

    private String selectServer(List<String> servers, String key) {
        if (servers == null || servers.isEmpty()) return zoneConfig.getLeaderIp();
        long hash = FNV_OFFSET;
        for (char c : key.toCharArray()) {
            hash ^= c;
            hash *= FNV_PRIME;
        }
        int idx = (int) Math.floorMod(hash, (long) servers.size());
        return servers.get(idx);
    }

    public String send(String ip, int port, String message) {
        if (ip == null || ip.isBlank()) return null;
        try (Socket socket = new Socket(ip, port)) {
            socket.setSoTimeout(SOCKET_TIMEOUT_MS);
            PrintWriter    pw = new PrintWriter(socket.getOutputStream(), true);
            BufferedReader br = new BufferedReader(new InputStreamReader(socket.getInputStream()));
            pw.println(message);
            return br.readLine();
        } catch (Exception e) {
            log.warn("[TCP] Failed to contact {}:{} — {}", ip, port, e.getMessage());
            return null;  // FIX: was returning "N/A" — null is more honest
        }
    }

    private boolean isHit(String r) {
        return r != null && !r.isBlank() && !"N/A".equals(r) && !r.startsWith("LEASE;");
    }
}
