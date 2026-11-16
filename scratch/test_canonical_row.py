CANONICAL_COLUMNS = {
    'rolename': 'RoleName',
    'employeeid': 'EmployeeID',
    'staffname': 'StaffName',
    'userid': 'UserID',
    'isactive': 'IsActive',
}

class PgRow(dict):
    def __init__(self, cols, values):
        super().__init__()
        self._values = list(values)
        for idx, col in enumerate(cols):
            low = col.lower()
            canon = CANONICAL_COLUMNS.get(low, col)
            dict.__setitem__(self, col, values[idx])
            dict.__setitem__(self, canon, values[idx])
            dict.__setitem__(self, low, values[idx])

r = PgRow(['rolename', 'employeeid', 'staffname'], ['Shop Manager', 1, 'Ramesh Sharma'])
d = dict(r)

assert d.get('RoleName') == 'Shop Manager'
assert d.get('rolename') == 'Shop Manager'
assert d['RoleName'] == 'Shop Manager'
assert d['EmployeeID'] == 1
assert d['StaffName'] == 'Ramesh Sharma'
print("ALL CANONICAL ROW TESTS PASSED!")
