#include "acl_manager.h"
#include <set>
#include <sstream>
#include <vector>
#include <iostream>


using namespace std;


bool check_acl(const string& client_ip) {
    std::cerr << "checking zone" << std::endl;
    stringstream ss(client_ip);
    string octet;
    vector<int> octets;

    while (getline(ss, octet, '.')) {
        octets.push_back(stoi(octet));  
    }

    if (octets.size() != 4) {
        return false; 
    }

    // checking if it fits withing range
    if (octets[0]==192 && octets[1]==168 && octets[2]<=13 && octets[2]>=10) {
        return true; 
    }

    return false; 
}
 
