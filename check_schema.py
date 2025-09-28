import sqlite3

conn = sqlite3.connect("library.db")
c = conn.cursor()

# Print schema of all tables
c.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
for row in c.fetchall():
    print(row[0], "=>", row[1])

conn.close()
