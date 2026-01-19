import socket
import json

class States:




    def __init__(self):

        self.selfRecords = set()
        self.selfIp = self.get_advertised_ip()
        self.nodes = {self.selfIp:1}
        self.rank = 1
        self.lastRank = 1
        self.updateRecordSet()
        self.leader = True
        self.beatInterval = 100
        self.leaderDead = 300
        self.nodeCount = len(self.nodes)
        self.leaderIp = self.selfIp
        self.updateState()




    def get_advertised_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Any reachable IP works; no packet is sent
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()



    def setLeaderIp (self, ip):
        self.leaderIp = ip
        self.updateState()

    def addNodes(self, ip):
        if ip in self.nodes: return 
        self.nodeCount+=1
        self.nodes[ip] = self.nodeCount
        self.lastRank = len(self.nodes)
        self.updateRecordSet()




    def removeNode(self, ip):
        del self.nodes[ip]
        self.nodeCount = len(self.nodes)
        i =1
        for ips in self.nodes.items():
            self.nodes[ips] = i 
            i+=1
        self.rank = self.nodes[self.selfIp]
        self.lastRank = len(self.nodes)
        self.updateRecordSet()
        



    def updateRank(self, rank, lastRank):
        self.rank = rank 
        self.lastRank = lastRank
        self.updateRecordSet()



    def updateRecordSet(self):
        lastRank, rank = self.lastRant, self.rank
        size = lastRank//rank 
        added = size*(rank-1)
        rem = lastRank%rank 
        if rem<rank:    added+=rem 
        else:   added+=rank-1
        if rem>=rank:   size+=1
        i = added 
        alp = 'abcdefghijklmnopqrstuvwxyz'
        tempRecords = set()
        while size:
            tempRecords.add(alp[i])
            i+=1
            size-=1
        self.selfRecords = tempRecords
        self.updateState()
        


    def to_state_dict(self):
        return {
            "selfIp": self.selfIp,
            "nodes": self.nodes,
            "rank": self.rank,
            "lastRank": self.lastRank,
            "leader": self.leader,
            "beatInterval": self.beatInterval,
            "leaderDead": self.leaderDead,
            "nodeCount": self.nodeCount,
            "leaderIp": self.leaderIp,
            "selfRecords": list(self.selfRecords)
        }


    def updateState(self):
        with open('../states.txt', 'w') as file:
            json.dump(self.to_state_dict(), file, indent=2)