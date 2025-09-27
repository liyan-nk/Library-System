import sqlite3

conn = sqlite3.connect('library.db')
c = conn.cursor()

# Backup old table (optional: only if table exists)
try:
    c.execute("ALTER TABLE transactions RENAME TO transactions_old;")
except:
    print("No old transactions table found, skipping rename.")

# Create new transactions table
c.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    book_id INTEGER,
    student_name TEXT,
    issue_date TEXT,
    return_date TEXT
)
''')

# Optional: copy old data if table existed
try:
    c.execute('''
    INSERT INTO transactions(book_id, student_name, issue_date, return_date)
    SELECT book_id, student_name, issue_date, return_date
    FROM transactions_old
    ''')
except:
    print("No old transactions data to copy.")

conn.commit()
conn.close()
print("Database upgraded successfully!")
