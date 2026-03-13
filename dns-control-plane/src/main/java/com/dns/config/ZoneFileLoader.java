package com.dns.config;

import com.dns.model.ZoneConfig;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.List;

/**
 * Loads cluster config at startup.
 *
 * Cache IPs come from lServers.txt.
 * Data plane contact point is always 127.0.0.1 (port-mapped via Docker).
 * The actual leader election happens inside Docker — we don't need to know
 * the real leader IP because any node forwards to the leader automatically.
 */
@Configuration
public class ZoneFileLoader {

    private static final Logger log = LoggerFactory.getLogger(ZoneFileLoader.class);

    @Value("${dns.zone.file:../lServers.txt}")
    private String zoneFilePath;

    @Bean
    public ZoneConfig zoneConfig() {
        File zoneFile = new File(zoneFilePath);

        ZoneConfig config;
        if (!zoneFile.exists()) {
            log.warn("[ZONE] lServers.txt not found — using localhost fallback");
            config = new ZoneConfig("127.0.0.1", List.of("127.0.0.1"), List.of("127.0.0.1"));
        } else {
            try {
                config = new ObjectMapper().readValue(zoneFile, ZoneConfig.class);
                log.info("[ZONE] Cache servers loaded: {}", config);
            } catch (IOException e) {
                throw new IllegalStateException("[ZONE] Failed to parse lServers.txt: " + e.getMessage(), e);
            }
        }

        // Always use 127.0.0.1 as the data plane contact point.
        // Port 8000 is mapped from node1 container to localhost via Docker.
        // Even if node1 is a follower it will forward to the real leader internally.
        config.setLeaderIp("127.0.0.1");
        log.info("[ZONE] Data plane contact point: 127.0.0.1:8000");

        return config;
    }
}