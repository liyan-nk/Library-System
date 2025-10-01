import sqlite3

conn = sqlite3.connect("library.db")
c = conn.cursor()

# Add 'available' column if it doesn't exist
try:
    c.execute("ALTER TABLE books ADD COLUMN available TEXT DEFAULT 'Yes'")
    print("✅ 'available' column added to books table")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("ℹ️ 'available' column already exists, skipping")
    else:
        raise

conn.commit()
conn.close()
