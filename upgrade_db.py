import sqlite3

conn = sqlite3.connect("library.db")
c = conn.cursor()

# ---------------------- BOOKS ----------------------
# Backup old table
try:
    c.execute("ALTER TABLE books RENAME TO books_old;")
except sqlite3.OperationalError:
    print("No old books table found, skipping rename.")

# Create new books table with UNIQUE constraint on name
c.execute('''
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    author TEXT
)
''')

# Copy old data (ignore duplicates)
try:
    c.execute('''
    INSERT OR IGNORE INTO books (name, author)
    SELECT name, author FROM books_old;
    ''')
except:
    print("No old books data to copy.")

# ---------------------- STUDENTS ----------------------
try:
    c.execute("ALTER TABLE students RENAME TO students_old;")
except sqlite3.OperationalError:
    print("No old students table found, skipping rename.")

c.execute('''
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admission_no TEXT UNIQUE,
    name TEXT,
    batch TEXT
)
''')

# Copy old data (ignore duplicates)
try:
    c.execute('''
    INSERT OR IGNORE INTO students (admission_no, name, batch)
    SELECT admission_no, name, batch FROM students_old;
    ''')
except:
    print("No old students data to copy.")

# ---------------------- TRANSACTIONS ----------------------
try:
    c.execute("ALTER TABLE transactions RENAME TO transactions_old;")
except sqlite3.OperationalError:
    print("No old transactions table found, skipping rename.")

c.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER,
    student_id INTEGER,
    issue_date TEXT,
    return_date TEXT,
    returned INTEGER DEFAULT 0,
    FOREIGN KEY(book_id) REFERENCES books(id),
    FOREIGN KEY(student_id) REFERENCES students(id)
)
''')

# Copy old data
try:
    c.execute('''
    INSERT OR IGNORE INTO transactions (book_id, student_id, issue_date, return_date, returned)
    SELECT book_id, student_id, issue_date, return_date, returned FROM transactions_old;
    ''')
except:
    print("No old transactions data to copy.")

conn.commit()
conn.close()
print("Database upgraded successfully with UNIQUE constraints!")
