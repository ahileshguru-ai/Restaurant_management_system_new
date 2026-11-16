import sqlite3

c = sqlite3.connect('restaurant.db')
c.row_factory = sqlite3.Row
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]

with open('database/schema_postgres.sql', 'r', encoding='utf-8') as f:
    pg_sql = f.read().lower()

missing = []
for t in tables:
    cols = [r['name'] for r in c.execute(f"PRAGMA table_info({t})").fetchall()]
    for col in cols:
        if col.lower() not in pg_sql:
            missing.append((t, col))
            print(f"MISSING in schema_postgres.sql: {t}.{col}")

if not missing:
    print("All SQLite columns exist in schema_postgres.sql!")
