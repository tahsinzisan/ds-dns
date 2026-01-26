#include "../include/zone_file_reader.h"

#include <fstream>
#include <iostream>
#include <string>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;
using namespace std;

ZoneFileReader::ZoneFileReader(const std::string& filename)
    : zone_file_path_(filename) {}

    bool ZoneFileReader::load_zone_file() {
        ifstream file(zone_file_path_);
        if (!file.is_open()) {
            return false;
        }
    
        json j;
        file >> j;
    
        leader_ip_ = j["leaderIp"].get<string>();
        l1_servers_ = j["l1Servers"].get<vector<string>>();
        l2_servers_ = j["l2Servers"].get<vector<string>>();
    
        return true;
    }
    

string ZoneFileReader::get_ip_for_domain(const string& key, bool is_internal) {
    if (is_internal) {
        return "1.1.1.1";
    }

    if (leader_ip_.empty()) {
        cerr << "No leader IP known" << endl;
        return "";
    }

    // ---------- l1 ----------
    string l1addr = keyHashL1(key);
    string response = com(l1addr, "GET;" + key);

    if (response != "N/A") {
        return response;
    }

    // ---------- l2 ----------
    string l2addr = keyHashL2(key);
    response = com(l2addr, "GET;" + key);
    // If value returned
    if (response.rfind("LEASE;", 0) != 0) {
        return response;
    }

    // ---------- lease handling ----------
    if (response == "LEASE;GRANTED") {
        // Only this requester goes to leader
        string value = com(leader_ip_, "GET;" + key);

        string set_msg = "SET;" + key + ";" + value;
        com(l2addr, set_msg);
        com(l1addr, set_msg);

        return value;
    }

    // ---------- lease wait ----------
    while (true) {
        response = com(l2addr, "GET;" + key);
        if (response.rfind("LEASE;", 0) != 0) {
            return response;
        }
        usleep(100000); // 100ms backoff
    }
}

string ZoneFileReader::com(const string& ip, const string& msg) {
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        cerr << "Socket creation failed" << endl;
        return "";
    }

    sockaddr_in serv_addr{};
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(8000);

    if (inet_pton(AF_INET, ip.c_str(), &serv_addr.sin_addr) <= 0) {
        cerr << "Invalid address: " << ip << endl;
        close(sock);
        return "";
    }

    if (connect(sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) < 0) {
        cerr << "Connection failed to " << ip << endl;
        close(sock);
        return "";
    }

    send(sock, msg.c_str(), msg.size(), 0);

    char buffer[1024] = {0};
    ssize_t n = read(sock, buffer, sizeof(buffer));

    close(sock);
    return (n > 0) ? string(buffer, n) : "";
}


size_t ZoneFileReader::simpleHash(const string& key) {
    const size_t fnv_offset = 1469598103934665603ULL;
    const size_t fnv_prime  = 1099511628211ULL;

    size_t hash = fnv_offset;
    for (char c : key) {
        hash ^= static_cast<size_t>(c);
        hash *= fnv_prime;
    }
    return hash;
}


string ZoneFileReader::keyHashL1(const string& key) {
    if (l1_servers_.empty()) return "";

    size_t idx = simpleHash(key) % l1_servers_.size();
    return l1_servers_[idx];
}

string ZoneFileReader::keyHashL2(const string& key) {
    if (l2_servers_.empty()) return "";

    size_t idx = simpleHash(key) % l2_servers_.size();
    return l2_servers_[idx];
}
