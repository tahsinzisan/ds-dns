class Reader:
    def __init__(self, _states):
        records = {}
        for record_head in _states.selfRecords:
            filepath = f'../records/{record_head}.txt'
            with open (filepath, 'r') as file:
                for line in file:
                    domain, rtype, value = line.strip().split(',')
                    records[(domain, rtype)] = value
        self.records = records
        print('record loaded on memory')
    
    def recordResponse(self, domain, rtype):
        if (domain, rtype) not in self.records:
            return 'fd'
        return self.records[(domain, rtype)]