package com.dns;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;

/**
 * DNS Control Plane entry point.
 *
 * This is a pure socket server - no Tomcat, no HTTP, no web server of any kind.
 * Spring Boot is used only for:
 *   - Dependency injection (@Autowired, @Component)
 *   - Configuration binding (@Value, application.properties)
 *   - Startup lifecycle (ApplicationRunner)
 *
 * All networking is raw Java UDP/TCP sockets managed directly by DnsServer.
 * This mirrors the original C++ Boost.Asio implementation exactly.
 *
 * Ports opened by this process:
 *   5353 UDP  - DNS query listener
 *   5353 TCP  - DNS query listener (RFC 1035 length-prefixed)
 */
@SpringBootApplication
public class DnsApplication {

    public static void main(String[] args) {
        new SpringApplicationBuilder(DnsApplication.class)
                .web(WebApplicationType.NONE)   // no Tomcat, no HTTP server
                .run(args);
    }
}
