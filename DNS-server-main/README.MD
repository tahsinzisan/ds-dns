 DNS Server

 Overview
This DNS server is designed to handle DNS queries over both UDP and TCP protocols. It supports dynamic domain resolution from a zone file, serving both internal and external IP addresses based on the request origin.

 Features
- UDP and TCP support: Listens for DNS queries over both UDP and TCP, using asynchronous operations.
- Internal/External DNS Resolution: Differentiates between internal and external DNS requests and responds accordingly.
- Zone File Support: Dynamically reads zone files to resolve domain names.
- Flexible ACL: Checks for internal IPs using an IP address range.

 Technology
The DNS server is built using the Boost.Asio library to handle both UDP and TCP connections asynchronously. The server listens on the same port (133) for both types of requests.

 Key Components

 1. DNS_Server
- The `DNS_Server` class is responsible for handling both UDP and TCP queries.
- It listens on the specified UDP and TCP ports and uses asynchronous functions to receive and respond to requests.
- Manages split DNS checks, zone file reading, and DNS response building.

 2. Asynchronous UDP Handling
- The server listens for incoming UDP requests using `async_receive_from` and processes them when received.
- The request is parsed, and a response is built depending on whether the query is internal or external.

 3. Asynchronous TCP Handling
- The server listens for incoming TCP connections using `async_accept`.
- When a connection is accepted, the server reads the request, builds a response, and sends it back over the TCP socket.

 4. Response Handling
- The response is constructed following the DNS message format.
- The server returns the appropriate flags and resource records based on the query.

 5. Zone File Resolution
- The server reads domain names from a zone file and resolves them dynamically based on the queried domain.
- It supports split DNS, where internal and external queries receive different IP addresses.

 6. ACL Handling
- The server uses an Access Control List (ACL) mechanism to differentiate between internal and external DNS requests.
- Provides the appropriate internal or external IP addresses based on the requester’s IP range.

 
