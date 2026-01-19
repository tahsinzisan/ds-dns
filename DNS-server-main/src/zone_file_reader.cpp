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

ZoneFileReader::ZoneFileReader(const std::string& filename) {
    zone_file_path_ = filename;
}

bool ZoneFileReader::load_zone_file() {
    ifstream file(zone_file_path_);
    if (!file.is_open()) {
        cerr << "Failed to open config file: " << zone_file_path_ << endl;
        return false;
    }

    try {
        json j;
        file >> j;


        if (j.contains("leaderIp") && !j["leaderIp"].is_null()) {
            leader_ip_ = j["leaderIp"].get<string>();
            cout << "Successfully loaded leader IP: " << leader_ip_ << endl;
        } else {
            cerr << "JSON error: 'leaderIp' not found in file." << endl;
            return false;
        }
    } catch (json::parse_error& e) {
        cerr << "JSON Parse error: " << e.what() << endl;
        return false;
    }

    file.close();
    return true;
}

string ZoneFileReader::get_ip_for_domain(string& domain, bool is_internal) {
    if (is_internal) {}
        return "1.1.1.1";
    }
    if (leader_ip_.empty()) {
        cerr << "Error: No leader IP known." << endl;
        return "";
    }

    int sock = 0;
    struct sockaddr_in serv_addr;
    char buffer[1024] = {0};

    // 1. Create Socket
    if ((sock = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
        cerr << "Socket creation error" << endl;
        return "";
    }

    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(8000);


    if (inet_pton(AF_INET, leader_ip_.c_str(), &serv_addr.sin_addr) <= 0) {
        cerr << "Invalid address/ Address not supported" << endl;
        close(sock);
        return "";
    }


    if (connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
        cerr << "Connection to leader failed at " << leader_ip_ << ":8000" << endl;
        close(sock);
        return "";
    }


    send(sock, domain.c_str(), domain.length(), 0);
    

    int valread = read(sock, buffer, 1024);
    string response = (valread > 0) ? string(buffer, valread) : "";

    close(sock);
    return response;
}