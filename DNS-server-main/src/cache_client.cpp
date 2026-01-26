#include "../include/cache_client.h"

#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>
#include <iostream>

CacheClient::CacheClient(const std::string& host, int port)
    : sockfd(-1), host(host), port(port) {
    connectToServer();
}

CacheClient::~CacheClient() {
    if (sockfd != -1) {
        close(sockfd);
    }
}

bool CacheClient::connectToServer() {
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd < 0) {
        perror("socket");
        return false;
    }

    sockaddr_in server_addr{};
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);

    if (inet_pton(AF_INET, host.c_str(), &server_addr.sin_addr) <= 0) {
        perror("inet_pton");
        return false;
    }

    if (connect(sockfd,
                reinterpret_cast<sockaddr*>(&server_addr),
                sizeof(server_addr)) < 0) {
        perror("connect");
        return false;
    }

    return true;
}

std::string CacheClient::sendCommand(const std::string& command) {
    std::string cmd = command + "\n";

    ssize_t sent = send(sockfd, cmd.c_str(), cmd.size(), 0);
    if (sent < 0) {
        perror("send");
        return "";
    }

    char buffer[1024];
    memset(buffer, 0, sizeof(buffer));

    ssize_t received = recv(sockfd, buffer, sizeof(buffer) - 1, 0);
    if (received < 0) {
        perror("recv");
        return "";
    }

    return std::string(buffer);
}

std::string CacheClient::get(const std::string& key) {
    std::string command = "GET;" + key;
    return sendCommand(command);
}

bool CacheClient::set(const std::string& key, const std::string& value) {
    std::string command = "SET;" + key + ";" + value;
    std::string response = sendCommand(command);
    return response.find("OK") != std::string::npos;
}
