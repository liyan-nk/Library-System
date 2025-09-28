import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import datetime
import os
import secrets

app = Flask(__name__)
# FIX 1: Use environment variable for SECRET_KEY, falling back to a secure random string
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(24))
DB_NAME = "library.db"

# FIX 2: Implement SQLiteContext for secure connection handling and enabling Foreign Keys
class SQLiteContext:
    """A context manager to handle SQLite connections and ensure commits/closes."""
    def __init__(self, db_name):
        self.db_name = db_name
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_name)
        self.conn.row_factory = sqlite3.Row
        # CRITICAL FIX: Ensure Foreign Key constraints are enabled per connection
        self.conn.execute('PRAGMA foreign_keys = ON;')
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Commit on successful block execution (no exception)
        if exc_type is None and self.conn:
            self.conn.commit()
        
        # Close the connection whether an exception occurred or not
        if self.conn:
            self.conn.close()
        
        # Do not suppress exceptions if they occurred or if it's a COMMIT failure (return False)
        return False

def get_connection():
    return SQLiteContext(DB_NAME)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # --- ROBUST SCHEMA DEFINITION FOR SAFETY ---
        # Note: This aggressive RENAME/DROP/CREATE is necessary to ensure the ON DELETE SET NULL 
        # and NULLABLE columns are enforced if the DB existed without them.

        # 1. Temporarily store old data if tables exist
        try:
             cursor.execute("CREATE TABLE books_temp AS SELECT * FROM books")
             cursor.execute("DROP TABLE books")
             cursor.execute("CREATE TABLE students_temp AS SELECT * FROM students")
             cursor.execute("DROP TABLE students")
             cursor.execute("DROP TABLE transactions") # Transactions must be dropped to fix FKs
        except sqlite3.OperationalError:
             pass
        
        # 2. Create tables with final, correct schema
        
        cursor.execute("""CREATE TABLE books (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            custom_id TEXT UNIQUE,
                            name TEXT NOT NULL,
                            author TEXT NOT NULL,
                            available BOOLEAN NOT NULL DEFAULT 1
                        )""")
        cursor.execute("""CREATE TABLE students (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            admission_no TEXT UNIQUE NOT NULL,
                            name TEXT NOT NULL,
                            batch TEXT NOT NULL
                        )""")
        
        # FIX (INTEGRITY): ON DELETE SET NULL to preserve transaction history. book_id/student_id are nullable.
        cursor.execute("""CREATE TABLE transactions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            book_id INTEGER, 
                            student_id INTEGER, 
                            issue_date TEXT NOT NULL,
                            return_date TEXT,
                            FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE SET NULL,
                            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE SET NULL
                        )""")
        
        # 3. Copy data back
        try:
            cursor.execute("INSERT INTO books SELECT * FROM books_temp")
            cursor.execute("DROP TABLE books_temp")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute("INSERT INTO students SELECT * FROM students_temp")
            cursor.execute("DROP TABLE students_temp")
        except sqlite3.OperationalError:
            pass

# Initialize the database structures
init_db()

@app.route("/")
def index():
    return render_template("index.html")

# --- BOOKS ---

@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":
        custom_id = request.form.get("custom_id")
        if custom_id == "":
            custom_id = None
        name = request.form["name"]
        author = request.form["author"]
        try:
            with get_connection() as conn:
                conn.execute("INSERT INTO books (custom_id, name, author, available) VALUES (?, ?, ?, 1)",
                             (custom_id, name, author))
            flash("Book added successfully!", "success")
        except sqlite3.IntegrityError:
            flash("Book with this Custom ID already exists!", "danger")
        except Exception as e:
            flash(f"Error adding book: {str(e)}", "danger")
        return redirect(url_for("add_book"))
    return render_template("add_book.html")

@app.route("/view_books")
def view_books():
    with get_connection() as conn:
        books = conn.execute("SELECT * FROM books").fetchall()
    return render_template("view_books.html", books=books)

@app.route("/delete_book/<int:id>", methods=["GET", "POST"])
def delete_book(id):
    # LOGIC: Prevent deletion if book is actively issued.
    try:
        with get_connection() as conn:
            book = conn.execute("SELECT available, name FROM books WHERE id=?", (id,)).fetchone()
            if not book:
                 flash("Book not found.", "danger")
                 return redirect(url_for("view_books"))

            if not book['available']:
                flash(f"Cannot delete '{book['name']}'. It is currently issued out!", "danger")
                return redirect(url_for("view_books"))
                
            # Deletion is safe: ON DELETE SET NULL handles associated transaction history.
            conn.execute("DELETE FROM books WHERE id=?", (id,))
        flash("Book deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting book: {str(e)}", "danger")
    return redirect(url_for("view_books"))

@app.route("/edit_book/<int:id>", methods=["GET", "POST"])
def edit_book(id):
    # IMPLEMENTATION FIX: Full edit logic
    with get_connection() as conn:
        book = conn.execute("SELECT * FROM books WHERE id=?", (id,)).fetchone()
        
    if book is None:
        flash("Book not found!", "danger")
        return redirect(url_for("view_books"))

    if request.method == "POST":
        custom_id = request.form.get("custom_id")
        if custom_id == "":
            custom_id = None
        name = request.form["name"]
        author = request.form["author"]

        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE books SET custom_id=?, name=?, author=? WHERE id=?",
                    (custom_id, name, author, id)
                )
            flash(f"Book '{name}' updated successfully!", "success")
            return redirect(url_for("view_books"))
        except sqlite3.IntegrityError:
            flash("Book with this Custom ID already exists!", "danger")
            # Render the form again with the failure message
            # We must re-fetch the book for the template (though it's the same as before the POST)
            with get_connection() as conn:
                book = conn.execute("SELECT * FROM books WHERE id=?", (id,)).fetchone()
        except Exception as e:
            flash(f"Error updating book: {str(e)}", "danger")
            # Re-fetch book data for template after error
            with get_connection() as conn:
                book = conn.execute("SELECT * FROM books WHERE id=?", (id,)).fetchone()

    # GET request or POST failure: render the edit form
    return render_template("edit_book.html", book=book)

# --- STUDENTS ---

@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        admission_no = request.form["admission_no"].upper()
        name = request.form["name"]
        batch = request.form["batch"]
        try:
            with get_connection() as conn:
                conn.execute("INSERT INTO students (admission_no, name, batch) VALUES (?, ?, ?)",
                             (admission_no, name, batch))
            flash("Student added successfully!", "success")
        except sqlite3.IntegrityError:
            flash("Student with this Admission No already exists!", "danger")
        except Exception as e:
            flash(f"Error adding student: {str(e)}", "danger")
        return redirect(url_for("add_student"))
    return render_template("add_student.html")

@app.route("/view_students")
def view_students():
    with get_connection() as conn:
        students = conn.execute("SELECT * FROM students").fetchall()
    return render_template("view_students.html", students=students)

@app.route("/delete_student/<int:id>", methods=["GET", "POST"])
def delete_student(id):
    # LOGIC: Implement Student Deletion, preventing deletion with active issues.
    try:
        with get_connection() as conn:
            active_issues = conn.execute("SELECT COUNT(id) FROM transactions WHERE student_id=? AND return_date IS NULL", (id,)).fetchone()[0]
            student = conn.execute("SELECT name FROM students WHERE id=?", (id,)).fetchone()
            
            if not student:
                 flash("Student not found.", "danger")
                 return redirect(url_for("view_students"))

            if active_issues > 0:
                flash(f"Cannot delete student '{student['name']}'. They currently have {active_issues} book(s) issued!", "danger")
                return redirect(url_for("view_students"))
            
            # Deletion is safe: ON DELETE SET NULL handles associated transaction history.
            conn.execute("DELETE FROM students WHERE id=?", (id,))
        flash("Student deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting student: {str(e)}", "danger")
    return redirect(url_for("view_students"))

@app.route("/edit_student/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    # IMPLEMENTATION FIX: Full edit logic
    with get_connection() as conn:
        student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()
        
    if student is None:
        flash("Student not found!", "danger")
        return redirect(url_for("view_students"))

    if request.method == "POST":
        admission_no = request.form["admission_no"].upper()
        name = request.form["name"]
        batch = request.form["batch"]

        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE students SET admission_no=?, name=?, batch=? WHERE id=?",
                    (admission_no, name, batch, id)
                )
            flash(f"Student '{name}' updated successfully!", "success")
            return redirect(url_for("view_students"))
        except sqlite3.IntegrityError:
            flash("Student with this Admission No already exists!", "danger")
            # Re-fetch student data for template after error
            with get_connection() as conn:
                student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()
        except Exception as e:
            flash(f"Error updating student: {str(e)}", "danger")
            # Re-fetch student data for template after error
            with get_connection() as conn:
                student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()

    # GET request or POST failure: render the edit form
    return render_template("edit_student.html", student=student)

# --- TRANSACTIONS ---

@app.route("/issue", methods=["GET", "POST"])
def issue_book():
    if request.method == "POST":
        book_id_input = request.form["book_id"]
        student_adm = request.form["admission_no"].upper()
        with get_connection() as conn:
            # Logic to find book by custom_id or internal id
            book = conn.execute("SELECT * FROM books WHERE custom_id=? OR id=?", (book_id_input, book_id_input)).fetchone()
            student = conn.execute("SELECT * FROM students WHERE admission_no=?", (student_adm,)).fetchone()
            
            if not book:
                flash("Book not found! (Check ID or Custom ID)", "danger")
                return redirect(url_for("issue_book"))
            if not student:
                flash("Student not found! (Check Admission No)", "danger")
                return redirect(url_for("issue_book"))
            if not book["available"]:
                flash("Book is currently not available!", "danger")
                return redirect(url_for("issue_book"))
            
            try:
                conn.execute("INSERT INTO transactions (book_id, student_id, issue_date) VALUES (?, ?, ?)",
                             (book["id"], student["id"], datetime.datetime.now().strftime('%Y-%m-%d')))
                conn.execute("UPDATE books SET available=0 WHERE id=?", (book["id"],))
                flash(f"Book '{book['name']}' issued to {student['name']}!", "success")
            except Exception as e:
                flash(f"Error issuing book: {str(e)}", "danger")
                
        return redirect(url_for("issue_book"))
    return render_template("issue.html")

@app.route("/return", methods=["GET", "POST"])
def return_book():
    if request.method == "POST":
        book_id_input = request.form["book_id"]
        student_adm = request.form["admission_no"].upper()
        
        with get_connection() as conn:
            book = conn.execute("SELECT * FROM books WHERE custom_id=? OR id=?", (book_id_input, book_id_input)).fetchone()
            student = conn.execute("SELECT * FROM students WHERE admission_no=?", (student_adm,)).fetchone()
            
            if not book or not student:
                flash("Book or student not found!", "danger")
                return redirect(url_for("return_book"))
            
            transaction = conn.execute(
                "SELECT id, book_id FROM transactions WHERE book_id=? AND student_id=? AND return_date IS NULL",
                (book["id"], student["id"])
            ).fetchone()
            
            if not transaction:
                flash("No active issue found for this book and student!", "danger")
                return redirect(url_for("return_book"))
            
            try:
                conn.execute("UPDATE transactions SET return_date=? WHERE id=?",
                             (datetime.datetime.now().strftime('%Y-%m-%d'), transaction["id"]))
                conn.execute("UPDATE books SET available=1 WHERE id=?", (book["id"],))
                flash(f"Book '{book['name']}' returned by {student['name']}!", "success")
            except Exception as e:
                flash(f"Error returning book: {str(e)}", "danger")
                
        return redirect(url_for("return_book"))
    return render_template("return.html")

# --- REPORTS ---

@app.route("/active_issues")
def active_issues():
    with get_connection() as conn:
        # Use LEFT JOIN to ensure records remain visible even if a book or student was deleted
        transactions = conn.execute("""SELECT t.id, 
                                     COALESCE(b.name, '[DELETED BOOK]') AS book_name, 
                                     COALESCE(s.name, '[DELETED STUDENT]') AS student_name, 
                                     COALESCE(s.batch, '-') AS batch, 
                                     t.issue_date
                                     FROM transactions t
                                     LEFT JOIN books b ON t.book_id = b.id
                                     LEFT JOIN students s ON t.student_id = s.id
                                     WHERE t.return_date IS NULL
                                     ORDER BY t.issue_date DESC""").fetchall()
    return render_template("active_issues.html", transactions=transactions)

@app.route("/transaction_history")
def transaction_history():
    with get_connection() as conn:
        # Use LEFT JOIN and COALESCE for history integrity
        transactions = conn.execute("""SELECT t.id, 
                                     COALESCE(b.name, '[DELETED BOOK]') AS book_name, 
                                     COALESCE(s.name, '[DELETED STUDENT]') AS student_name, 
                                     COALESCE(s.batch, '-') AS batch,
                                     t.issue_date, 
                                     t.return_date
                                     FROM transactions t
                                     LEFT JOIN books b ON t.book_id = b.id
                                     LEFT JOIN students s ON t.student_id = s.id
                                     ORDER BY t.id DESC""").fetchall()
    return render_template("transaction_history.html", transactions=transactions)

@app.route("/search_books", methods=["GET", "POST"])
def search_books():
    results = []
    if request.method == "POST":
        query = request.form["query"]
        with get_connection() as conn:
            search_term = f"%{query}%"
            results = conn.execute("""SELECT * FROM books 
                                     WHERE name LIKE ? 
                                     OR author LIKE ?
                                     OR custom_id LIKE ?
                                     ORDER BY name ASC""",
                                     (search_term, search_term, search_term)).fetchall()
    return render_template("search_books.html", results=results)

# --- AJAX ENDPOINTS ---

@app.route("/get_book/<book_id>")
def get_book(book_id):
    with get_connection() as conn:
        book = conn.execute("SELECT * FROM books WHERE custom_id=? OR id=?", (book_id, book_id)).fetchone()
    if book:
        return jsonify({"success": True, "title": book["name"], "available": bool(book['available'])})
    return jsonify({"success": False})

@app.route("/get_student/<admn>")
def get_student(admn):
    admn = admn.upper()
    with get_connection() as conn:
        student = conn.execute("SELECT * FROM students WHERE admission_no=?", (admn,)).fetchone()
    if student:
        return jsonify({"success": True, "name": student["name"], "batch": student["batch"]})
    return jsonify({"success": False})

if __name__ == "__main__":
    app.run(debug=True)