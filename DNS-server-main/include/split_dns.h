#ifndef SPLIT_DNS_H
#define SPLIT_DNS_H

#include <string>

bool is_internal_request(const std::string& client_ip);

#endif 
