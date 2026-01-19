#include "../include/dns_server.h"
#include "../include/split_dns.h"
#include "../include/dns_response.h"
#include <boost/asio.hpp>
#include <iostream>
#include <memory>
#include <unordered_map>
#include <deque>
#include <chrono>

using namespace boost::asio;
using namespace boost::asio::ip;
using namespace std;

// ---- Rate Limiting Structures ---- //
using TimePoint = std::chrono::steady_clock::time_point;
unordered_map<string, deque<TimePoint>> rate_limit_map;

bool is_rate_limited(const string& ip) {
    const int MAX_QUERIES = 5;
    const int TIME_WINDOW_SECONDS = 10;

    auto now = std::chrono::steady_clock::now();
    auto& timestamps = rate_limit_map[ip];

    while (!timestamps.empty() &&
           std::chrono::duration_cast<std::chrono::seconds>(now - timestamps.front()).count() > TIME_WINDOW_SECONDS) {
        timestamps.pop_front();
    }

    if (timestamps.size() >= MAX_QUERIES) {
        return true;
    }

    timestamps.push_back(now);
    return false;
}

// ---- DNS Server Implementation ---- //

DNS_Server::DNS_Server(boost::asio::io_context& io, int udp_port, int tcp_port, ZoneFileReader& zone_file_reader)
    : udp_socket_(io, udp::endpoint(udp::v4(), udp_port)),
      tcp_acceptor_(io, tcp::endpoint(tcp::v4(), tcp_port)),
      io_service_(io),
      zone_file_reader_(zone_file_reader)
{
    recv_buffer_.resize(1024);
    start_receive();
    start_accept();
}

void DNS_Server::run() {
    io_service_.run();
}

void DNS_Server::start_receive() {
    std::cerr << "udp socket start" << std::endl;
    udp_socket_.async_receive_from(
        buffer(recv_buffer_), remote_endpoint_,
        [this](boost::system::error_code ec, size_t bytes_recvd) {
            if (!ec && bytes_recvd >= 12) {
                handle_udp_request(bytes_recvd);
            }
            start_receive();
        });
}

void DNS_Server::handle_udp_request(size_t bytes_recvd) {
    std::cerr << "handle udp" << std::endl;
    string query(recv_buffer_.begin(), recv_buffer_.begin() + bytes_recvd);

    string client_ip = remote_endpoint_.address().to_string();
    if (is_rate_limited(client_ip)) {
        std::cerr << "UDP request from " << client_ip << " rate-limited" << std::endl;
        return;
    }

    bool is_internal = is_internal_request(client_ip);
    string host = parse_domain(vector<uint8_t>(recv_buffer_.begin(), recv_buffer_.begin() + bytes_recvd));
    string ip_address = zone_file_reader_.get_ip_for_domain(host, is_internal);
    std::cerr << ip_address << std::endl;
    string response = build_response(query, ip_address);
    std::cerr << response << std::endl;
    print_hex(response);
    send_udp_response(response);
}

void DNS_Server::send_udp_response(const string& response) {
    std::cerr << "sending udp response" << std::endl;
    udp_socket_.async_send_to(buffer(response), remote_endpoint_,
        [](boost::system::error_code, size_t) {});
}

void DNS_Server::start_accept() {
    std::cerr << "tcp socket start" << std::endl;
    auto socket = make_shared<tcp::socket>(io_service_);
    tcp_acceptor_.async_accept(*socket, [this, socket](boost::system::error_code ec) {
        if (!ec) {
            handle_tcp_request(*socket);
        }
        start_accept(); // Accept next connection
    });
}

void DNS_Server::handle_tcp_request(tcp::socket& tcp_socket) {
    std::cerr << "tcp handle" << std::endl;
    try {
        uint8_t length_bytes[2];
        boost::asio::read(tcp_socket, buffer(length_bytes, 2));
        uint16_t msg_length = (length_bytes[0] << 8) | length_bytes[1];

        vector<uint8_t> request(msg_length);
        boost::asio::read(tcp_socket, buffer(request.data(), msg_length));

        string client_ip = tcp_socket.remote_endpoint().address().to_string();
        if (is_rate_limited(client_ip)) {
            std::cerr << "TCP request from " << client_ip << " rate-limited" << std::endl;
            tcp_socket.close();
            return;
        }

        bool is_internal = is_internal_request(client_ip);
        string host = parse_domain(request);
        string ip_address = zone_file_reader_.get_ip_for_domain(host, is_internal);
        string response = build_response(string(request.begin(), request.begin() + msg_length), ip_address);

        send_tcp_response(response, tcp_socket);
    } catch (const exception& e) {
        cerr << "TCP error: " << e.what() << endl;
        tcp_socket.close();
    }
}

void DNS_Server::send_tcp_response(const string& response, tcp::socket& tcp_socket) {
    boost::system::error_code ec;
    uint16_t response_len = response.size();
    uint8_t length_prefix[2] = {
        static_cast<uint8_t>((response_len >> 8) & 0xFF),
        static_cast<uint8_t>(response_len & 0xFF)
    };
    vector<boost::asio::const_buffer> buffers = {
        boost::asio::buffer(length_prefix, 2),
        boost::asio::buffer(response)
    };
    boost::asio::write(tcp_socket, buffers, ec);
}

string DNS_Server::parse_domain(const vector<uint8_t>& request) {
    std::cerr << "parsing domain" << std::endl;
    string domain;
    size_t pos = 12;

    while (pos < request.size()) {
        uint8_t len = request[pos];
        if (len == 0) break;
        pos++;
        if (pos + len > request.size()) break;
        domain += string(request.begin() + pos, request.begin() + pos + len) + ".";
        pos += len;
    }

    if (!domain.empty() && domain.back() == '.') {
        domain.pop_back();
    }

    return domain;
}

void DNS_Server::print_hex(const string& data) {
    for (unsigned char c : data) {
        printf("%02x ", c);
    }
    printf("\n");
}
