package com.dns.dns;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Parses DNS wire-format query packets (RFC 1035).
 *
 * Mirrors the original C++ parse_domain() method in dns_server.cpp.
 *
 * DNS message layout:
 *   Bytes 0-1   Transaction ID
 *   Bytes 2-3   Flags
 *   Bytes 4-5   QDCOUNT
 *   Bytes 6-7   ANCOUNT
 *   Bytes 8-9   NSCOUNT
 *   Bytes 10-11 ARCOUNT
 *   Byte  12+   Question section: QNAME + QTYPE + QCLASS
 *
 * QNAME encoding: each label is preceded by a 1-byte length.
 * A zero byte terminates the name.
 * Example: "example.com" → [7]example[3]com[0]
 */
@Component
public class DnsRequestParser {

    private static final Logger log = LoggerFactory.getLogger(DnsRequestParser.class);

    /**
     * Extracts the queried domain name from raw DNS query bytes.
     *
     * @param request raw DNS query bytes
     * @return domain name string e.g. "example.com", or null if malformed
     */
    public String parseDomain(byte[] request) {
        if (request == null || request.length < 12) {
            log.warn("[PARSER] Request too short: {} bytes", request == null ? 0 : request.length);
            return null;
        }

        StringBuilder domain = new StringBuilder();
        int pos = 12; // QNAME starts at byte 12

        try {
            while (pos < request.length) {
                int labelLen = request[pos] & 0xFF;

                if (labelLen == 0) break;                  // root label - end of QNAME

                if ((labelLen & 0xC0) == 0xC0) break;     // compression pointer - not in queries

                pos++;
                if (pos + labelLen > request.length) {
                    log.warn("[PARSER] Label overflows packet boundary");
                    return null;
                }

                if (domain.length() > 0) domain.append('.');
                domain.append(new String(request, pos, labelLen));
                pos += labelLen;
            }
        } catch (Exception e) {
            log.error("[PARSER] Exception: {}", e.getMessage());
            return null;
        }

        String result = domain.toString().toLowerCase();
        log.debug("[PARSER] Domain: '{}'", result);
        return result.isEmpty() ? null : result;
    }

    /**
     * Extracts the QTYPE from the DNS query.
     * 1 = A, 28 = AAAA, 15 = MX etc.
     * Returns -1 if unreadable.
     */
    public int parseQType(byte[] request) {
        if (request == null || request.length < 12) return -1;
        int pos = 12;
        try {
            while (pos < request.length) {
                int labelLen = request[pos] & 0xFF;
                if (labelLen == 0) { pos++; break; }
                pos += 1 + labelLen;
            }
            if (pos + 1 >= request.length) return -1;
            return ((request[pos] & 0xFF) << 8) | (request[pos + 1] & 0xFF);
        } catch (Exception e) {
            return -1;
        }
    }
}
