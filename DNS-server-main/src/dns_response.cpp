#include <iostream>
#include <sstream>
#include <arpa/inet.h>
using namespace std;

string build_response(const string& query, const string& ip_address) {
    ostringstream response;

    if (query.size() < 12) {
        cerr << "Query too short" << endl;
        return "";
    }

    // Transaction ID (2 bytes)
    response.write(query.data(), 2);

    // Flags (2 bytes)
    if (ip_address.empty()) {
        // QR=1, Opcode=0, AA=1, TC=0, RD=0, RA=0, Z=0, RCODE=3 (NXDOMAIN)
        uint16_t flags = htons(0x8183);
        response.write(reinterpret_cast<const char*>(&flags), 2);
    } else {
        // QR=1, Opcode=0, AA=1, TC=0, RD=0, RA=0, Z=0, RCODE=0 (No error)
        uint16_t flags = htons(0x8180);
        response.write(reinterpret_cast<const char*>(&flags), 2);
    }

    // QDCOUNT (1 question)
    uint16_t qdcount = htons(1);
    response.write(reinterpret_cast<const char*>(&qdcount), 2);

    // ANCOUNT (1 if IP found, else 0)
    uint16_t ancount = htons(ip_address.empty() ? 0 : 1);
    response.write(reinterpret_cast<const char*>(&ancount), 2);

    // NSCOUNT (0)
    uint16_t nscount = 0;
    response.write(reinterpret_cast<const char*>(&nscount), 2);

    // ARCOUNT (0)
    uint16_t arcount = 0;
    response.write(reinterpret_cast<const char*>(&arcount), 2);

    // Find end of QNAME in question section
    size_t qname_end = 12;
    while (qname_end < query.size() && query[qname_end] != 0x00) {
        qname_end++;
    }
    if (qname_end >= query.size()) {
        cerr << "Malformed question section" << endl;
        return "";
    }

    // Copy QNAME + QTYPE (2 bytes) + QCLASS (2 bytes)
    size_t question_len = (qname_end - 12) + 1 + 4; // labels + zero + QTYPE + QCLASS
    if (12 + question_len > query.size()) {
        cerr << "Malformed question length" << endl;
        return "";
    }
    response.write(query.data() + 12, question_len);

    if (!ip_address.empty()) {
        // Answer section

        // Use pointer to QNAME in question (offset 12 = 0x0c)
        char pointer[2] = { static_cast<char>(0xc0), 0x0c };
        response.write(pointer, 2);

        // TYPE A (0x0001)
        uint16_t type = htons(1);
        response.write(reinterpret_cast<const char*>(&type), 2);

        // CLASS IN (0x0001)
        uint16_t class_in = htons(1);
        response.write(reinterpret_cast<const char*>(&class_in), 2);

        // TTL (60 seconds)
        uint32_t ttl = htonl(60);
        response.write(reinterpret_cast<const char*>(&ttl), 4);

        // RDLENGTH (4 bytes for IPv4)
        uint16_t rdlength = htons(4);
        response.write(reinterpret_cast<const char*>(&rdlength), 2);

        // RDATA (IPv4 address)
        struct in_addr addr;
        if (inet_pton(AF_INET, ip_address.c_str(), &addr) != 1) {
            cerr << "Invalid IP address: " << ip_address << endl;
            return "";
        }
        response.write(reinterpret_cast<const char*>(&addr.s_addr), 4);
    }

    return response.str();
}
