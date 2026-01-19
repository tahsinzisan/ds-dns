#ifndef ACL_MANAGER_H
#define ACL_MANAGER_H
#include <boost/asio.hpp>

#include <string>

bool check_acl(const std::string& client_ip);

#endif 
