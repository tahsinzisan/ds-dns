
#include "split_dns.h"
#include "acl_manager.h"
#include <string>

bool is_internal_request(const std::string& client_ip) {
    return check_acl(client_ip);  // Check ACL for internal access
}
