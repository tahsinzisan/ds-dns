class Reader:
    def __init__(self, _states):
        self._states = _states
        records = {}
        for record_head in _states.selfRecords:
            filepath = f'../records/{record_head}.txt'
            try:
                with open(filepath, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        parts = line.split(',')
                        if len(parts) == 3:
                            domain, rtype, value = parts
                            records[(domain.strip(), rtype.strip())] = value.strip()
            except FileNotFoundError:
                print(f'[READER] Warning: {filepath} not found — skipping')
        self._states.records = records
        print(f'[READER] Loaded {len(records)} records covering shards: {_states.selfRecords}')

    def recordResponse(self, domain, rtype):
        """Return IP for (domain, rtype), or 'N/A' if not found on this node."""
        if not domain or domain[0].lower() not in self._states.selfRecords:
            return 'N/A'   # FIX: was returning None (implicit) — caused TypeError
        key = (domain.strip().lower(), rtype.strip().upper())
        return self._states.records.get(key, 'N/A')  # FIX: was 'N/R' — treated as valid IP
