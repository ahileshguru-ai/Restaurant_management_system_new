"""
PostgreSQL Adapter & Compatibility Verification Test
===================================================
Tests that PgRow and PgCursor correctly translate SQLite-style DB-API calls:
1. Case-insensitive column and index access via PgRow
2. Automatic ? -> %s placeholder replacement
3. Automatic GROUP_CONCAT -> STRING_AGG conversion
4. Automatic RETURNING <pk> injection for lastrowid capture
"""

import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database.db import PgRow, PgCursor, TABLE_PRIMARY_KEYS


class DummyRawCursor:
    def __init__(self):
        self.last_query = None
        self.last_params = None
        self.description = None
        self._fetched = None

    def execute(self, sql, params=None):
        self.last_query = sql
        self.last_params = params
        if "RETURNING" in sql:
            self.description = [("id", None)]
            self._fetched = (42,)
        elif "SELECT" in sql:
            self.description = [("employeeid", None), ("name", None)]
            self._fetched = (101, "Test Chef")
        else:
            self.description = None
            self._fetched = None

    def fetchone(self):
        return self._fetched

    def fetchall(self):
        return [self._fetched] if self._fetched else []


def test_adapter():
    print("Testing PgRow wrapper...")
    row = PgRow(["employeeid", "name", "salary"], [5, "Rahul Varma", 24000.00])
    assert row["EmployeeID"] == 5, "Case-insensitive lookup failed"
    assert row["employeeid"] == 5, "Exact lookup failed"
    assert row[0] == 5, "Integer index lookup failed"
    assert row["Name"] == "Rahul Varma", "Name lookup failed"
    assert row[1] == "Rahul Varma", "Index 1 failed"
    assert row.get("NonExistent", "Default") == "Default", "Default get failed"
    assert dict(row)["name"] == "Rahul Varma", "dict() conversion failed"
    print("  [OK] PgRow behaves identically to sqlite3.Row")

    print("Testing PgCursor SQL translation...")
    raw = DummyRawCursor()
    cur = PgCursor(raw, None)

    # 1. Parameter placeholder translation
    cur.execute("SELECT * FROM Users WHERE UserID = ? AND RoleID = ?;", (1, 2))
    assert "%s" in raw.last_query, "Failed to translate ? to %s"
    assert "?" not in raw.last_query, "Leftover ? placeholder"
    print("  [OK] ? -> %s translation verified")

    # 2. GROUP_CONCAT translation
    cur.execute("SELECT GROUP_CONCAT(DISTINCT ot.TableNumber) AS Tables FROM Order_Tables ot;")
    assert "STRING_AGG(DISTINCT ot.TableNumber::text, ',')" in raw.last_query, "Failed GROUP_CONCAT conversion"
    print("  [OK] GROUP_CONCAT -> STRING_AGG translation verified")

    # 3. INSERT INTO lastrowid RETURNING injection
    cur.execute("INSERT INTO Staff (Name, RoleID, Salary) VALUES (?, ?, ?);", ("Vikram", 3, 40000.00))
    assert "RETURNING employeeid;" in raw.last_query, "Failed to inject RETURNING employeeid;"
    assert cur.lastrowid == 42, f"Expected lastrowid=42, got {cur.lastrowid}"
    print("  [OK] INSERT RETURNING pk injection and lastrowid capture verified")

    # 4. SELECT result wrapping
    cur.execute("SELECT EmployeeID, Name FROM Staff WHERE EmployeeID = %s;", (101,))
    res = cur.fetchone()
    assert res["EmployeeID"] == 101, "Failed to wrap row in PgRow"
    print("  [OK] fetchone() automatically wraps in PgRow")

    print("\nALL POSTGRESQL ADAPTER TESTS PASSED!")


if __name__ == "__main__":
    test_adapter()
