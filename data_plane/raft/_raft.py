import asyncio
import threading
import time
import ipaddress
import socket



class Raft:
    def __init__(self, _states):
        self.currLogNum = 0
        self._states = _states
        self.currLogNum
        asyncio.run(self.client())
        self.followerCount
        self.leader = True
        self.beatInterval = 1
        self.leaderDead = 1
        self.beatSent = False
     
        task = threading.Thread(target=self.raftHeart, args=())
        task.start()
        print('raft crated')




    def beatHandler(self, beat):
        self.leaderDead = self._states.leaderDead
        leaderIp, logN, rank, lastRank = beat.strip().split(';')
        self._states.addNodes(leaderIp)
        if not self.beatSent: return

        if self.leader:

            ldIp = ipaddress.IPv4Address(leaderIp)
            myIp = ipaddress.IPv4Address(self._states.selfIp)
            
            if int(logN)>self.currLogNum:
                self.leader = False
                self._states.setLeaderIp(leaderIp)
            elif logN==self.currLogNum and ldIp>myIp:
                self.leader = False
                self._states.setLeaderIp(leaderIp)
        
        if not self.leader:
            if self._states.rank == rank and self._states.lastRank == lastRank: return
            self._states.updateRank(rank, lastRank)
        



    def raftHeart(self):
        while True:
            time.sleet(1)
            self.beatInterval-=1
            self.leaderDead -= 1
            if self.beatInterval == 0:
                if self.leader:
                    
                    self.sendBeat()
                    self.leaderDead = self._states.leaderDead
                self.beatInterval = self._states.beatInterval
            if self.leaderDead == 0:
                self._states.removeNode(self._states.leaderIp)
                self._states.setLeaderIp = self._states.selfIp
                
                self.leader = True
                self.sendBeat()
                self.beatInterval = self._states.beatInterval
                self.leaderDead = self._states.leaderDead


   
  
    def sendBeat(self):
        self.beatSent = True
        msg = f'{self._states.selfIp};{self.currLogNum}'
        self.sendToFollower(7000,msg)

 
 
 
    async def client(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", 8000)
        writer.write(b"hello server\n")
        await writer.drain()
        print((await reader.readline()).decode().strip())
        writer.close()

    



    def sendCommit(self, num):
        msg = f'4;{num}'
        self.sendToFollower(9000,msg)
        print('commit send')

    
    
    def sendLog(self, log, num):
        self.currLogNum = num
        self.sendToFollower(9000,log)
    
    
    
    def sendAck(self, num):
        msg = f'3;{num}'
        if self.leader: return 
        s = socket.socket()
        s.connect((self._states.leaderIp, 9000))
        s.sendall(msg.encode())
        s.close()

        
    def sendRead(self, domain):
        if self._states.leader:
            self.sendToFollower(8000, domain+'\n')


    def sendToFollower(self, port, msg):
        nodes = self._states.nodes
        ogMsg = msg
        for ip, rank in nodes.items():
            if ip == self._states.selfIp: continue
            if port == 7000:
                msg += f';{rank};{self._states.lastRank}'
            s = socket.socket()
            s.connect((ip, port))
            msg+='\n'
            s.sendall(msg.encode())
            s.close()
            msg = ogMsg