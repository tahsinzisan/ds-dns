import json 
import socket


def sendUpdate(domain, ip, leaderIp):
    update = f'{domain},A,{ip}\n'
    s = socket.socket()
    s.connect((leaderIp, 7000))
    s.sendall(update.encode())
    s.close()



with open ('./states.txt','r') as file:
    data  = json.load(file)
selfRecords = data['selfRecords']

for head in selfRecords:
    filepath = f'{head}.txt'
    with open (filepath, 'r') as file:
        for line in file:
            domain, rtype, record = line.strip().split(',')
            try:
                ip = socket.gethostbyname(domain)
                if ip != record:
                    sendUpdate(domain, ip, data['leaderIp'])
            except socket.gaierror as e:
                continue