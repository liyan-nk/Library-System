# create_tables.py
import sqlite3

conn = sqlite3.connect("library.db")
c = conn.cursor()

# Create books table
c.execute('''
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    author TEXT
)
''')

# Create students table
c.execute('''
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admission_no TEXT UNIQUE,
    name TEXT,
    batch TEXT
)
''')

# Create transactions table
c.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT UNIQUE,
    book_id INTEGER,
    student_id INTEGER,
    issue_date TEXT,
    return_date TEXT,
    returned INTEGER DEFAULT 0,
    FOREIGN KEY(book_id) REFERENCES books(id),
    FOREIGN KEY(student_id) REFERENCES students(id)
)
''')

conn.commit()
conn.close()
print("All tables created successfully!")
