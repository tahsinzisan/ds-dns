#include "../include/dns_server.h"
#include "../include/zone_file_reader.h"
#include <boost/asio.hpp>
#include <iostream>
using namespace boost::asio;
using namespace std;

int main() {
    
    ZoneFileReader zone_reader("zone.txt");
    if (!zone_reader.load_zone_file()) {
        std::cerr << "Failed to load zone file!" << std::endl;
        return -1; 
    }

    try {
        boost::asio::io_context io_service;
        DNS_Server server(io_service, 133, 133, zone_reader);  // pass zone_reader here
        server.run();
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
    }

    return 0;
}
