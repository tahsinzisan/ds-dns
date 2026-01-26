import socket
from collections import defaultdict

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"
BG_RED = "\033[41m"

def commit(records, num):

    with open('last.txt', 'w') as f:
        f.write(str(num))
    for head, record in records.items():
        filepath = f'{head}.txt'
        with open(filepath, 'a') as file:
            file.writelines(record)
    print(f'{BG_RED}{YELLOW}{BOLD}||||||||||||||||||||||||||||||||||||New commit done at num {num}|||||||||||||||||||||||||||||||||||||{RESET}')

def missingCommit(start, num):
    with open('missing.txt', 'w') as f:
        f.write(f'{start};{num}')



def parseStart(start):
    with open('top-1m.csv', 'r') as file:
        records = defaultdict(list)
        errStart = 0
        contErr = 0
        for line in file:
            num, domain = line.strip().split(',')
            num = int(num)
            if num<=start: continue
            print(f'Asking A record for {domain}; {num}')
            try:
                ip = socket.gethostbyname(domain)
                records[domain[0]].append(f'{domain},A,{ip}\n')
                if contErr >200:
                    parseStart(errStart)
                contErr = 0
            except Exception as e:
                print(f"Failed to resolve {RED}{domain}: {e}{RESET}")
                if not contErr:
                    errStart = num
                    contErr = 1
                else:
                    contErr+=1
                        
            if not num%100:
                commit(records, num)
                records = defaultdict(list)


    '''with open('result.txt','w') as file:
        lines = []
        for head, record in records.items():
            lines.extend(record)
        file.writelines(lines)'''


'''start = 0
try:
    with open("last.txt", "r") as f:
        try:
            start = int(f.read())
        except ValueError:
            start = 0
except FileNotFoundError:
    start = 0
'''



r = {}
with open('top-1m.csv', 'r') as file:
    for line in file:
        num, domain = line.strip().split(',')
        r[domain] = int(num)

start = 0
for head in 'abcdefghijklmnopqrstuvwxyz0123456789':
    try:
        with open(f'{head}.txt', 'r') as file:
            for line in file:
                domain, _, _ = line.split(',')
                start = max(r[domain], start)

    except Exception as e:
        continue

parseStart(start+1)


