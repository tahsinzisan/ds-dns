package com.dns.dns;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.net.InetAddress;
import java.net.UnknownHostException;

/**
 * Builds DNS wire-format response packets (RFC 1035).
 *
 * Mirrors the original C++ build_response() function in dns_response.cpp.
 *
 * Supports:
 *   - Type A response  (IP address found)    → flags 0x8180, ANCOUNT=1
 *   - NXDOMAIN response (domain not found)   → flags 0x8183, ANCOUNT=0
 */
@Component
public class DnsResponseBuilder {

    private static final Logger log = LoggerFactory.getLogger(DnsResponseBuilder.class);
    private static final int TTL_SECONDS = 60;

    /**
     * Builds a complete DNS response packet.
     *
     * @param query     original raw DNS query bytes
     * @param ipAddress resolved IPv4 address, or null/empty for NXDOMAIN
     * @return DNS response bytes, or null on error
     */
    public byte[] buildResponse(byte[] query, String ipAddress) {
        log.info("inside responsebuilder");
        if (query == null || query.length < 12) {
            log.warn("[RESPONSE] Query too short to build response");
            return null;
        }

        boolean found = ipAddress != null && !ipAddress.isBlank();

        try (ByteArrayOutputStream baos = new ByteArrayOutputStream();
             DataOutputStream out = new DataOutputStream(baos)) {

            // -- Header (12 bytes) --

            // Transaction ID - copy from query bytes 0-1
            out.write(query[0]);
            out.write(query[1]);

            // Flags
            // found:     QR=1 AA=1 RCODE=0 (No Error)  → 0x8180
            // not found: QR=1 AA=1 RCODE=3 (NXDOMAIN)  → 0x8183
            out.writeShort(found ? 0x8180 : 0x8183);

            out.writeShort(1);              // QDCOUNT = 1 question
            out.writeShort(found ? 1 : 0); // ANCOUNT = 1 if found, else 0
            out.writeShort(0);              // NSCOUNT = 0
            out.writeShort(0);              // ARCOUNT = 0

            // -- Question section - copy QNAME + QTYPE + QCLASS from query --
            // Find the null terminator of QNAME
            int qnameEnd = 12;
            while (qnameEnd < query.length && (query[qnameEnd] & 0xFF) != 0) {
                qnameEnd++;
            }
            if (qnameEnd >= query.length) {
                log.warn("[RESPONSE] Malformed QNAME - no null terminator");
                return null;
            }

            // Copy: QNAME (qnameEnd-12 bytes) + null byte (1) + QTYPE (2) + QCLASS (2)
            int questionLen = (qnameEnd - 12) + 1 + 4;
            if (12 + questionLen > query.length) {
                log.warn("[RESPONSE] Insufficient bytes for QTYPE/QCLASS");
                return null;
            }
            out.write(query, 12, questionLen);

            // -- Answer section (only if IP found) --
            if (found) {
                // Name pointer back to QNAME in question section (offset 12 = 0x0C)
                out.writeByte(0xC0);
                out.writeByte(0x0C);

                out.writeShort(1);          // TYPE  A = 1
                out.writeShort(1);          // CLASS IN = 1
                out.writeInt(TTL_SECONDS);  // TTL
                out.writeShort(4);          // RDLENGTH = 4 bytes for IPv4

                // RDATA - 4 bytes of IPv4 address
                try {
                    byte[] addr = InetAddress.getByName(ipAddress).getAddress();
                    out.write(addr);
                } catch (UnknownHostException e) {
                    log.error("[RESPONSE] Invalid IP '{}': {}", ipAddress, e.getMessage());
                    return null;
                }
            }

            return baos.toByteArray();

        } catch (IOException e) {
            log.error("[RESPONSE] IOException: {}", e.getMessage());
            return null;
        }
    }
}
