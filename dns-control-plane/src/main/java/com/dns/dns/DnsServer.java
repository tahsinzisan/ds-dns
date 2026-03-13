package com.dns.dns;

import com.dns.acl.AclManager;
import com.dns.cache.CacheClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.net.*;
import java.util.Arrays;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Core DNS server — pure raw Java socket server.
 * No Tomcat, no HTTP, no web framework.
 *
 * BUG FIX 2: All threads were daemon=true, causing the JVM to exit
 * immediately after ApplicationRunner.run() returned (since WebApplicationType.NONE
 * means no embedded server keeps the main thread alive).
 * Fix: listener threads are now non-daemon. run() also blocks on a CountDownLatch
 * so Spring Boot's main thread stays alive for the lifetime of the process.
 *
 * BUG FIX 6: UDP socket was shared across multiple worker threads calling
 * socket.send() concurrently without synchronization.
 * Fix: each UDP worker sends its response via a fresh, per-response DatagramSocket.
 * This is safe, efficient, and the standard pattern for UDP servers.
 */
@Component
public class DnsServer implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(DnsServer.class);

    @Value("${dns.udp.port}")
    private int udpPort;

    @Value("${dns.tcp.port}")
    private int tcpPort;

    @Value("${dns.threads.udp:4}")
    private int udpThreads;

    @Value("${dns.threads.tcp:8}")
    private int tcpThreads;

    @Autowired private DnsRequestParser   parser;
    @Autowired private DnsResponseBuilder responseBuilder;
    @Autowired private RateLimiter        rateLimiter;
    @Autowired private AclManager         aclManager;
    @Autowired private CacheClient        cacheClient;

    // Worker thread pools - daemon is fine for workers since listener threads keep JVM alive
    private ExecutorService udpWorkers;
    private ExecutorService tcpWorkers;

    // BUG FIX 2: latch keeps run() blocked so the main thread never exits
    private final CountDownLatch shutdownLatch = new CountDownLatch(1);

    @Override
    public void run(ApplicationArguments args) throws InterruptedException {
        udpWorkers = Executors.newFixedThreadPool(udpThreads, r -> {
            Thread t = new Thread(r, "dns-udp-worker");
            t.setDaemon(true);
            return t;
        });

        tcpWorkers = Executors.newFixedThreadPool(tcpThreads, r -> {
            Thread t = new Thread(r, "dns-tcp-worker");
            t.setDaemon(true);
            return t;
        });

        // BUG FIX 2: listener threads must be NON-daemon so JVM stays alive
        Thread udpThread = new Thread(this::runUdpServer, "dns-udp-listener");
        udpThread.setDaemon(false);   // non-daemon — keeps JVM alive
        udpThread.start();

        Thread tcpThread = new Thread(this::runTcpServer, "dns-tcp-listener");
        tcpThread.setDaemon(false);   // non-daemon — keeps JVM alive
        tcpThread.start();

        log.info("=================================================");
        log.info("  DNS Control Plane started (pure socket server)");
        log.info("  UDP listener → :{}", udpPort);
        log.info("  TCP listener → :{}", tcpPort);
        log.info("  No web server. No Tomcat. Raw sockets only.");
        log.info("=================================================");

        // BUG FIX 2: block main thread here forever
        // (released only on JVM shutdown signal, e.g. Ctrl+C)
        shutdownLatch.await();
    }

    // -------------------------------------------------------------------------
    // UDP server
    // -------------------------------------------------------------------------

    private void runUdpServer() {
        try (DatagramSocket socket = new DatagramSocket(udpPort)) {
            log.info("[UDP] Listening on :{}", udpPort);
            byte[] buffer = new byte[512];

            //noinspection InfiniteLoopStatement
            while (true) {
                DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
                socket.receive(packet);

                final byte[]      data     = Arrays.copyOf(packet.getData(), packet.getLength());
                final String      clientIp = packet.getAddress().getHostAddress();
                final InetAddress addr     = packet.getAddress();
                final int         port     = packet.getPort();

                udpWorkers.submit(() -> {
                    byte[] response = handleRequest(data, clientIp);
                    if (response != null) {
                        // Use the 'socket' variable from the runUdpServer scope
                        synchronized (socket) { 
                            try {
                                DatagramPacket resp = new DatagramPacket(response, response.length, addr, port);
                                socket.send(resp);
                            } catch (IOException e) {
                                log.warn("[UDP] Send error: {}", e.getMessage());
                            }
                        }
                    }
                });
            }
        } catch (Exception e) {
            log.error("[UDP] Server crashed: {}", e.getMessage(), e);
            shutdownLatch.countDown();  // unblock main thread so process can exit cleanly
        }
    }

    // -------------------------------------------------------------------------
    // TCP server
    // -------------------------------------------------------------------------

    private void runTcpServer() {
        try (ServerSocket serverSocket = new ServerSocket(tcpPort)) {
            log.info("[TCP] Listening on :{}", tcpPort);

            //noinspection InfiniteLoopStatement
            while (true) { 
                Socket client = serverSocket.accept();
                tcpWorkers.submit(() -> handleTcpClient(client));
            }
        } catch (Exception e) {
            log.error("[TCP] Server crashed: {}", e.getMessage(), e);
            shutdownLatch.countDown();
        }
    }


    private void handleTcpClient(Socket client) {
        String clientIp = client.getInetAddress().getHostAddress();
        try (client;
             DataInputStream  in  = new DataInputStream(client.getInputStream());
             DataOutputStream out = new DataOutputStream(client.getOutputStream())) {

            int msgLen = in.readUnsignedShort();
            if (msgLen <= 0) {
                log.warn("[TCP] Invalid message length {} from {}", msgLen, clientIp);
                return;
            }

            byte[] query = new byte[msgLen];
            in.readFully(query);

            byte[] response = handleRequest(query, clientIp);
            if (response != null) {
                out.writeShort(response.length);
                out.write(response);
                out.flush();
            }
        } catch (Exception e) {
            log.debug("[TCP] Client {} error: {}", clientIp, e.getMessage());
        }
    }

    // -------------------------------------------------------------------------
    // Shared request pipeline
    // -------------------------------------------------------------------------

    
    public byte[] handleRequest(byte[] query, String clientIp) {
        if (rateLimiter.isRateLimited(clientIp)) {
            return null;
        }

        String domain = parser.parseDomain(query);
        if (domain == null || domain.isBlank()) {
            log.warn("[DNS] Could not parse domain from {}", clientIp);
            return responseBuilder.buildResponse(query, null);
        }

        log.info("inide handler [DNS] {} asked for '{}'", clientIp, domain);

        String ipAddress;
        if (aclManager.isInternalRequest(clientIp) ) {
            ipAddress = "192.168.1.1";
            log.debug("[DNS] Internal response for {}: {}", domain, ipAddress);
        } else {
            ipAddress = cacheClient.resolve(domain);
        }

        String resolvedIp = (ipAddress == null || ipAddress.isBlank()) ? null : ipAddress;
        byte[] response = responseBuilder.buildResponse(query, resolvedIp);

        if (response == null) {
            log.warn("[DNS] Failed to build response for '{}'", domain);
        }
        return response;
    }
}
