package com.dns.acl;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Access Control List manager for split-DNS.
 *
 * Internal clients receive the private/internal IP address.
 * External clients receive the public IP address from the data plane.
 *
 * Mirrors the original C++ acl_manager.cpp + split_dns.cpp logic.
 *
 * Internal subnet is configurable via application.properties:
 *   dns.acl.subnet-prefix  = first two octets  (default: 192.168)
 *   dns.acl.octet3-min     = third octet min   (default: 10)
 *   dns.acl.octet3-max     = third octet max   (default: 13)
 *
 * So by default: 192.168.10.* through 192.168.13.* are internal.
 */
@Component
public class AclManager {

    private static final Logger log = LoggerFactory.getLogger(AclManager.class);

    @Value("${dns.acl.subnet-prefix:192.168}")
    private String subnetPrefix;

    @Value("${dns.acl.octet3-min:10}")
    private int octet3Min;

    @Value("${dns.acl.octet3-max:13}")
    private int octet3Max;

    /**
     * Returns true if the client IP belongs to the internal subnet.
     * Internal clients receive private IP addresses (split-DNS).
     */
    public boolean isInternalRequest(String clientIp) {
        log.info("inside acl");
        
        if (clientIp == null || clientIp.isBlank()) return false;

        String[] parts = clientIp.split("\\.");
        if (parts.length != 4) return false;

        try {
            String firstTwo = parts[0] + "." + parts[1];
            if (!firstTwo.equals(subnetPrefix)) return false;

            int thirdOctet = Integer.parseInt(parts[2]);
            boolean internal = thirdOctet >= octet3Min && thirdOctet <= octet3Max;

            if (internal) log.debug("[ACL] {} → INTERNAL", clientIp);
            return internal;

        } catch (NumberFormatException e) {
            log.warn("[ACL] Cannot parse IP '{}': {}", clientIp, e.getMessage());
            return false;
        }
    }
}
