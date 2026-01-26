#include <nlohmann/json.hpp>

class ZoneFileReader {
private:
    std::string zone_file_path_;
    std::string leader_ip_;
    std::vector<std::string> l1_servers_;
    std::vector<std::string> l2_servers_;

public:
    ZoneFileReader(const std::string& filename);

    bool load_zone_file();
    std::string get_ip_for_domain(const std::string& key, bool is_internal);

    std::string keyHashL1(const std::string& key);
    std::string keyHashL2(const std::string& key);

    std::string com(const std::string& ip, const std::string& msg);
};
