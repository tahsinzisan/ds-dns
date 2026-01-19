from collections import defaultdict


class Writer:
    def __init__(self):
        self.logs = defaultdict(str)
        self.logAck = defaultdict(int)
 
    def writeHandler(self, query, _raft):
        self._raft = _raft
        queryList = query.strip().split(';')
        type = queryList[0]
        if type == '1':
            update = queryList[1]
            _raft.currLogNum+=1
            num = str(_raft.currLogNum)
        
        if type == '2':
            type, num, update = queryList
        else:
            type, num = queryList 
            update = 'N/A'
        
        if type == '1':
            self.writeStarter(update, num)

        if type == '2':
            self.logs[num] = update
            _raft.sendAck(num)
        

        if type == '3':
            self.ackHandler(num, update)
        
        if type == '4':
            self.commitHandler(num)
        
        return ''
        

    def writeStarter(self, update):
        logN = self._raft.currLogNum
        log = f'2;{logN};{update}'
        self.logs[logN] = update
        self._raft.sendLog(log, logN)

    def ackHandler(self, num):
        self.logAck[num]+=1
        if self.logAck[num] == self._raft.followerCount:
            
            self._raft.sendCommit(num)
            self.commitHandler(num)

        


    def commitHandler(self, num):
        update = self.logs[num]
        domain = update.strip().split(',')[0]
        filepath = f'../records/{update[0]}.txt'
        tempFile = []
        with open (filepath, 'r') as file:
            for line in file:
                if line.strip().split(',')[0] == domain:
                    tempFile.append(update+'\n')
                    continue
                tempFile.append(line)
            
        with open (filepath, 'w') as file:
            file.writelines(tempFile)