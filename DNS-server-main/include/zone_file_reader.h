#ifndef ZONE_FILE_READER_H
#define ZONE_FILE_READER_H

#include <string>
#include <map>
using namespace std;

class ZoneFileReader {
public:
    ZoneFileReader(const string& zone_file_path);
    bool load_zone_file();
    string get_ip_for_domain(string& domain, bool is_internal);

private:
    string zone_file_path_;
    map<string, pair<string, string>> zone_records_;

};

#endif 
