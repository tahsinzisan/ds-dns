#ifndef CACHE_CLIENT_H
#define CACHE_CLIENT_H

#include <string>

class CacheClient {
public:
    CacheClient(const std::string& host, int port);
    ~CacheClient();

    std::string get(const std::string& key);
    bool set(const std::string& key, const std::string& value);

private:
    int sockfd;
    std::string host;
    int port;

    bool connectToServer();
    std::string sendCommand(const std::string& command);
};

#endif // CACHE_CLIENT_H
