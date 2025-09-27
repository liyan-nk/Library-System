from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
from datetime import datetime
import random
import string
import flash

app = Flask(__name__)
DB_NAME = 'library.db'

# ----------------- Database connection -----------------
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ----------------- Database initialization -----------------
def init_db():
    conn = get_db_connection()
    # Books table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            author TEXT
        )
    ''')
    # Students table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admission_no TEXT UNIQUE,
            name TEXT,
            batch TEXT
        )
    ''')
    # Transactions table
    conn.execute('''
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

# Initialize DB
init_db()

# ----------------- Home -----------------
@app.route('/')
def index():
    return render_template('index.html')

# ----------------- Add Book -----------------
@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        title = request.form['title'].strip()
        author = request.form['author'].strip()
        
        if not title or not author:
            flash("Title and Author are required!", "danger")
            return redirect(url_for('add_book'))

        conn = get_db_connection()
        conn.execute('INSERT INTO books (title, author, available) VALUES (?, ?, ?)',
                     (title, author, 'Yes'))  # default availability is Yes
        conn.commit()
        conn.close()
        
        flash(f'Book "{title}" added successfully!', 'success')
        return redirect(url_for('view_books'))

    return render_template('add_book.html')

# ----------------- View Books -----------------
@app.route('/view_books')
def view_books():
    conn = get_db_connection()
    books = conn.execute('SELECT * FROM books').fetchall()
    conn.close()
    return render_template('view_books.html', books=books)

# ----------------- Search Books -----------------
@app.route('/search_books', methods=['GET', 'POST'])
def search_books():
    results = []
    if request.method == 'POST':
        query = request.form['query']
        conn = get_db_connection()
        results = conn.execute('SELECT * FROM books WHERE name LIKE ?', ('%'+query+'%',)).fetchall()
        conn.close()
    return render_template('search_books.html', results=results)

# ----------------- Delete Book -----------------
@app.route('/delete_book/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    conn = get_db_connection()
    # Check if book is issued
    issued = conn.execute('SELECT * FROM transactions WHERE book_id=? AND returned=0', (book_id,)).fetchone()
    if issued:
        conn.close()
        return "Cannot delete: Book is currently issued."
    conn.execute('DELETE FROM books WHERE id=?', (book_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('view_books'))

# ----------------- Add Student -----------------
@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        admn_no = request.form['admission_no'].strip()
        name = request.form['name'].strip()
        batch = request.form['batch'].strip()

        if not admn_no or not name or not batch:
            flash("All fields are required!", "danger")
            return redirect(url_for('add_student'))

        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO students (admission_no, name, batch) VALUES (?, ?, ?)',
                         (admn_no, name, batch))
            conn.commit()
            flash(f"Student '{name}' added successfully!", 'success')
        except sqlite3.IntegrityError:
            flash(f"Student with admission no '{admn_no}' already exists!", 'danger')
        finally:
            conn.close()

        return redirect(url_for('view_students'))

    return render_template('add_student.html')

# ----------------- View Students -----------------
@app.route('/view_students')
def view_students():
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('view_students.html', students=students)

# ----------------- Issue Book -----------------
def generate_transaction_id(book_id, student_id):
    date_str = datetime.now().strftime('%Y%m%d')
    rand_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"T{date_str}{book_id}{student_id}{rand_str}"

@app.route('/issue', methods=['GET', 'POST'])
def issue_book():
    conn = get_db_connection()
    if request.method == 'POST':
        book_id = request.form['book_id'].strip()
        admission_no = request.form['admission_no'].strip()

        # Check book
        book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
        if not book or book['available'] == 'No':
            flash("Book not available or doesn't exist.", "danger")
            return redirect(url_for('issue_book'))

        # Check student
        student = conn.execute('SELECT * FROM students WHERE admission_no = ?', (admission_no,)).fetchone()
        if not student:
            flash("Student not found!", "danger")
            return redirect(url_for('issue_book'))

        # Insert transaction
        conn.execute('INSERT INTO transactions (book_id, student_id, issued_on, returned) VALUES (?, ?, DATE("now"), 0)',
                     (book_id, student['id']))
        # Update availability
        conn.execute('UPDATE books SET available = "No" WHERE id = ?', (book_id,))
        conn.commit()
        conn.close()
        flash(f'Book "{book["title"]}" issued to {student["name"]}', 'success')
        return redirect(url_for('active_issues'))

    books = conn.execute('SELECT * FROM books').fetchall()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('issue.html', books=books, students=students)

# ----------------- Return Book -----------------
@app.route('/return', methods=['GET', 'POST'])
def return_book():
    conn = get_db_connection()
    if request.method == 'POST':
        book_id = request.form['book_id'].strip()
        admission_no = request.form['admission_no'].strip()

        student = conn.execute('SELECT * FROM students WHERE admission_no = ?', (admission_no,)).fetchone()
        if not student:
            flash("Student not found!", "danger")
            return redirect(url_for('return_book'))

        transaction = conn.execute(
            'SELECT * FROM transactions WHERE book_id=? AND student_id=? AND returned=0',
            (book_id, student['id'])
        ).fetchone()

        if not transaction:
            flash("No active issue found for this book and student.", "danger")
            return redirect(url_for('return_book'))

        # Update transaction and book
        conn.execute('UPDATE transactions SET returned=1, returned_on=DATE("now") WHERE id=?', (transaction['id'],))
        conn.execute('UPDATE books SET available="Yes" WHERE id=?', (book_id,))
        conn.commit()
        conn.close()
        flash("Book returned successfully!", "success")
        return redirect(url_for('active_issues'))

    books = conn.execute('SELECT * FROM books').fetchall()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('return.html', books=books, students=students)

# ----------------- Active Issues -----------------
@app.route('/active_issues')
def active_issues():
    conn = get_db_connection()
    transactions = conn.execute('''
        SELECT t.id, b.name AS book_name, s.name AS student_name, s.batch, t.issue_date
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        JOIN students s ON t.student_id = s.id
        WHERE t.returned=0
    ''').fetchall()
    conn.close()
    return render_template('active_issues.html', transactions=transactions)

# ----------------- Transaction History -----------------
@app.route('/transaction_history')
def transaction_history():
    conn = get_db_connection()
    transactions = conn.execute('''
        SELECT t.id, t.transaction_id, b.name AS book_name, s.name AS student_name, s.batch, t.issue_date, t.return_date
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        JOIN students s ON t.student_id = s.id
    ''').fetchall()
    conn.close()
    return render_template('transaction_history.html', transactions=transactions)

# ----------------- Autofill APIs -----------------
@app.route('/get_book/<int:book_id>')
def get_book(book_id):
    conn = get_db_connection()
    book = conn.execute('SELECT * FROM books WHERE id=?', (book_id,)).fetchone()
    conn.close()
    if book:
        return jsonify({'success': True, 'name': book['name']})
    else:
        return jsonify({'success': False, 'message': 'Book not found!'})

@app.route('/get_student/<admission_no>')
def get_student(admission_no):
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE admission_no=?', (admission_no,)).fetchone()
    conn.close()
    if student:
        return jsonify({'success': True, 'name': student['name'], 'batch': student['batch']})
    else:
        return jsonify({'success': False, 'message': 'Student not found!'})

# ----------------- Run App -----------------
if __name__ == '__main__':
    app.run(debug=True)
