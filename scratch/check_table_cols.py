import re
import sqlite3

c = sqlite3.connect('restaurant.db')
c.row_factory = sqlite3.Row

with open('database/schema_postgres.sql', 'r', encoding='utf-8') as f:
    pg_sql = f.read()

# Extract CREATE TABLE blocks
table_blocks = re.findall(r'CREATE TABLE\s+([a-zA-Z0-9_]+)\s*\((.*?)\);', pg_sql, re.DOTALL)

for tbl_name, block in table_blocks:
    sqlite_cols = [r['name'] for r in c.execute(f"PRAGMA table_info({tbl_name})").fetchall()]
    block_lower = block.lower()
    for col in sqlite_cols:
        # Check if col is in block
        if not re.search(r'\b' + col.lower() + r'\b', block_lower):
            print(f"MISSING in table '{tbl_name}': column '{col}'")
