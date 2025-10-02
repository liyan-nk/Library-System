import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
import datetime
import os
import secrets
from functools import wraps 
from datetime import date, timedelta 
import hashlib 
import math 

app = Flask(__name__)
@app.template_filter('dateformat')
def dateformat(value, format='%d/%m/%y'):
    """Formats a date string from YYYY-MM-DD to a custom format."""
    if value is None:
        return "-"
    try:
        # Assumes the date is stored as YYYY-MM-DD in the database
        date_obj = datetime.datetime.strptime(value, '%Y-%m-%d')
        return date_obj.strftime(format)
    except (ValueError, TypeError):
        # If the format is already different, return it as is
        return value
# Secure configuration
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(24))
DB_NAME = "library.db"

# --- HELPER FUNCTION FOR TRUNCATION ---
def truncate_text(text, max_length=35):
    """Truncates text to a max length and adds an ellipsis."""
    if text and len(text) > max_length:
        return text[:max_length].strip() + '...'
    return text

# --- Hardcoded Librarian Credentials (Used for demonstration) ---
LIBRARIAN_USERNAME = os.environ.get('LIBRARIAN_USER', 'librarian')
LIBRARIAN_PASSWORD = os.environ.get('LIBRARIAN_PASS', 'password') 
# --------------------------------------------------------

# --- Hashing Utilities for Student Authentication ---
def hash_password(password):
    """Hashes a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(hashed_password, provided_password):
    """Checks a provided password against a hashed one."""
    return hashed_password == hash_password(provided_password)

# --- SQLite Context Manager for safe database connections ---
class SQLiteContext:
    """A context manager to handle SQLite connections and ensure commits/closes."""
    def __init__(self, db_name):
        self.db_name = db_name
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_name)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys = ON;')
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and self.conn:
            self.conn.commit()
        if self.conn:
            self.conn.close()
        return False

def get_connection():
    return SQLiteContext(DB_NAME)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # --- Database Schema Creation ---
        
        # Books Table (No change)
        cursor.execute("""CREATE TABLE IF NOT EXISTS books (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            custom_id TEXT UNIQUE,
                            name TEXT NOT NULL,
                            author TEXT NOT NULL,
                            available BOOLEAN NOT NULL DEFAULT 1
                        )""")
        
        # Students Table (No change)
        cursor.execute("""CREATE TABLE IF NOT EXISTS students (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            admission_no TEXT UNIQUE NOT NULL,
                            name TEXT NOT NULL,
                            batch TEXT NOT NULL
                        )""")
        
        # --- THIS IS THE UPDATED TABLE ---
        # Transactions Table (with ON DELETE SET NULL)
        cursor.execute("""CREATE TABLE IF NOT EXISTS transactions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            book_id INTEGER, 
                            student_id INTEGER, 
                            issue_date TEXT NOT NULL,
                            due_date TEXT NOT NULL,  
                            return_date TEXT,
                            FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE SET NULL,
                            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE SET NULL
                        )""")
        
        # Student Authentication Table (No change)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students_auth (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admission_no TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_approved BOOLEAN NOT NULL DEFAULT 0,
                FOREIGN KEY(admission_no) REFERENCES students(admission_no) ON DELETE CASCADE
            )
        """)

# Initialize the database structures
init_db()

# --- Context Processor for Pending Count ---
@app.context_processor
def inject_pending_count():
    with get_connection() as conn:
        try:
            count = conn.execute("SELECT COUNT(id) FROM students_auth WHERE is_approved = 0").fetchone()[0]
            return dict(pending_count=count)
        except:
            return dict(pending_count=0)

# ----------------- MAIN PORTAL SELECTION ROUTE -----------------

@app.route("/")
def select_portal():
    if session.get('logged_in'): return redirect(url_for('index'))
    if session.get('student_logged_in'): return redirect(url_for('student_dashboard'))
    return render_template("select_portal.html")

# ----------------- LIBRARIAN AUTH DECORATOR AND ROUTES -----------------

# --- LIBRARIAN ROUTES ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/librarian_login', methods=['GET', 'POST']) 
def login():
    if session.get('logged_in'):
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == LIBRARIAN_USERNAME and password == LIBRARIAN_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            flash('Librarian Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('librarian_login.html') 

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('select_portal'))

@app.route("/index")
@login_required 
def index():
    with get_connection() as conn:
        stats = conn.execute("SELECT (SELECT COUNT(id) FROM books) AS total_books, (SELECT COUNT(id) FROM students) AS total_students, (SELECT COUNT(id) FROM transactions WHERE return_date IS NULL) AS active_loans").fetchone()
        overdue_loans = conn.execute("SELECT b.name AS book_name, s.name AS student_name, s.admission_no, t.due_date FROM transactions t JOIN books b ON t.book_id = b.id JOIN students s ON t.student_id = s.id WHERE t.return_date IS NULL AND t.due_date < date('now') ORDER BY t.due_date ASC").fetchall()
        leaderboard_students = conn.execute("SELECT s.name, COUNT(t.id) as book_count FROM transactions t JOIN students s ON t.student_id = s.id GROUP BY t.student_id ORDER BY book_count DESC LIMIT 5").fetchall()
        chart_data_query = conn.execute("SELECT b.name, COUNT(t.id) as borrow_count FROM transactions t JOIN books b ON t.book_id = b.id GROUP BY t.book_id ORDER BY borrow_count DESC LIMIT 5").fetchall()

    # --- UPDATED: Process data for Chart.js with truncation ---
    chart_labels = [truncate_text(row['name']) for row in chart_data_query]
    chart_data = [row['borrow_count'] for row in chart_data_query]

    return render_template("index.html", 
                           total_books=stats['total_books'], total_students=stats['total_students'], active_loans=stats['active_loans'],
                           overdue_loans=overdue_loans, leaderboard_students=leaderboard_students,
                           chart_labels=chart_labels, chart_data=chart_data)

    # Process data for Chart.js
    chart_labels = [row['name'] for row in chart_data_query]
    chart_data = [row['borrow_count'] for row in chart_data_query]

    return render_template("index.html", 
                           total_books=stats['total_books'],
                           total_students=stats['total_students'],
                           active_loans=stats['active_loans'],
                           overdue_loans=overdue_loans,
                           leaderboard_students=leaderboard_students,
                           chart_labels=chart_labels,
                           chart_data=chart_data)

# ----------------- STUDENT AUTH DECORATOR AND ROUTES -----------------

def student_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('student_logged_in'):
            flash('Please log in to access the student portal.', 'danger')
            return redirect(url_for('student_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/student_register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        # Collect all necessary fields for the student record
        admission_no = request.form['admission_no'].strip().upper()
        name = request.form['name'].strip()
        batch = request.form['batch'].strip()
        password = request.form['password']
        
        if not all([admission_no, name, batch, password]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('student_register'))

        with get_connection() as conn:
            # 1. Check if the Admission No is already in the system (either table)
            existing_student = conn.execute("SELECT 1 FROM students WHERE admission_no=?", (admission_no,)).fetchone()
            if existing_student:
                # If the admission exists, check if it's already registered for the portal
                existing_auth = conn.execute("SELECT is_approved FROM students_auth WHERE admission_no=?", (admission_no,)).fetchone()
                
                if existing_auth and existing_auth['is_approved']:
                    flash("An account already exists and is approved. Please log in.", 'warning')
                elif existing_auth and not existing_auth['is_approved']:
                    flash("An account already exists and is pending approval. Please wait for the librarian.", 'warning')
                else:
                     # This scenario shouldn't happen with ON DELETE CASCADE, but handles manual insertions
                    flash("Student record exists, but portal account hasn't been created/approved. See librarian.", 'warning')
                return redirect(url_for('student_register'))
            
            try:
                # 2. CREATE the student record (profile) first
                conn.execute("INSERT INTO students (admission_no, name, batch) VALUES (?, ?, ?)",
                             (admission_no, name, batch))
                                 
                # 3. CREATE the authentication record
                hashed_pass = hash_password(password)
                conn.execute("INSERT INTO students_auth (admission_no, password_hash, is_approved) VALUES (?, ?, 0)",
                             (admission_no, hashed_pass))
                                 
                flash('Registration successful! Please wait for the librarian to approve your account before logging in.', 'success')
                return redirect(url_for('student_login'))
            except sqlite3.IntegrityError:
                # This should be caught by the check above, but for robustness
                flash(f"Admission Number '{admission_no}' is already registered.", 'danger')
                return redirect(url_for('student_register'))
            except Exception as e:
                flash(f'An error occurred during registration: {str(e)}', 'danger')
                return redirect(url_for('student_register'))

    return render_template('student_register.html')

@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if session.get('student_logged_in'):
        return redirect(url_for('student_dashboard'))
        
    if request.method == 'POST':
        # Ensure the input is stripped and capitalized, matching how it was saved.
        admission_no = request.form['admission_no'].strip().upper()
        password = request.form['password']

        if not admission_no:
              flash('Please enter your Admission Number.', 'danger')
              return redirect(url_for('student_login'))
        
        with get_connection() as conn:
            # Query students_auth table using the standardized admission_no
            auth_record = conn.execute("SELECT admission_no, password_hash, is_approved FROM students_auth WHERE admission_no=?", (admission_no,)).fetchone()
            
            if not auth_record:
                # If the admission_no is not in students_auth
                flash('Account not found. Have you registered?', 'danger')
            elif not auth_record['is_approved']:
                flash('Your account is awaiting approval by the librarian.', 'warning')
            elif check_password(auth_record['password_hash'], password):
                session['student_logged_in'] = True
                session['student_adm_no'] = auth_record['admission_no']
                flash('Login successful!', 'success')
                return redirect(url_for('student_dashboard'))
            else:
                # This handles incorrect password
                flash('Invalid Admission No or Password.', 'danger')
    
    return render_template('student_login.html')

@app.route('/student_logout')
def student_logout():
    session.pop('student_logged_in', None)
    session.pop('student_adm_no', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('select_portal'))

@app.route('/student_dashboard')
@student_login_required
def student_dashboard():
    student_adm_no = session.get('student_adm_no')
    with get_connection() as conn:
        student_record = conn.execute("SELECT id, name, batch FROM students WHERE admission_no=?", (student_adm_no,)).fetchone()
        if not student_record:
            flash("Could not find your student profile.", "danger")
            return redirect(url_for('student_logout'))
        student_id = student_record['id']
        active_loans = conn.execute("SELECT t.due_date < date('now') AS is_overdue, t.issue_date, t.due_date, COALESCE(b.name, '[DELETED BOOK]') AS book_name FROM transactions t LEFT JOIN books b ON t.book_id = b.id WHERE t.student_id = ? AND t.return_date IS NULL ORDER BY t.due_date ASC", (student_id,)).fetchall()
        loan_history = conn.execute("SELECT t.issue_date, t.return_date, COALESCE(b.name, '[DELETED BOOK]') AS book_name FROM transactions t LEFT JOIN books b ON t.book_id = b.id WHERE t.student_id = ? AND t.return_date IS NOT NULL ORDER BY t.return_date DESC", (student_id,)).fetchall()
        leaderboard_students = conn.execute("SELECT s.name, COUNT(t.id) as book_count FROM transactions t JOIN students s ON t.student_id = s.id GROUP BY t.student_id ORDER BY book_count DESC LIMIT 5").fetchall()
        chart_data_query = conn.execute("SELECT b.name, COUNT(t.id) as borrow_count FROM transactions t JOIN books b ON t.book_id = b.id GROUP BY t.book_id ORDER BY borrow_count DESC LIMIT 5").fetchall()
    
    # --- UPDATED: Process data for Chart.js with truncation ---
    chart_labels = [truncate_text(row['name']) for row in chart_data_query]
    chart_data = [row['borrow_count'] for row in chart_data_query]

    return render_template('student_dashboard.html', 
                           active_loans=active_loans, loan_history=loan_history, student_info=student_record,
                           leaderboard_students=leaderboard_students, chart_labels=chart_labels, chart_data=chart_data)



# ----------------- STUDENT BOOK SEARCH ROUTE (FIXED) -----------------

@app.route("/student_search_books", methods=["GET"])
@student_login_required 
def student_search_books():
    student_adm_no = session.get('student_adm_no')
    
    with get_connection() as conn:
        student_info = conn.execute("SELECT id, name, batch FROM students WHERE admission_no=?", (student_adm_no,)).fetchone()
        
        availability = conn.execute("SELECT SUM(CASE WHEN available = 1 THEN 1 ELSE 0 END) AS available_count, COUNT(id) AS total_count FROM books").fetchone()

        active_loans = conn.execute("""
            SELECT b.name AS book_name, t.issue_date, t.due_date, t.due_date < date('now') AS is_overdue
            FROM transactions t
            JOIN books b ON t.book_id = b.id
            WHERE t.student_id = ? AND t.return_date IS NULL
            ORDER BY t.due_date ASC
        """, (student_info['id'],)).fetchall()
        
    return render_template("student_search_results.html", 
                           student_info=student_info,
                           availability=availability,
                           active_loans=active_loans)


# ----------------- LIBRARIAN MANAGEMENT ROUTES -----------------

@app.route("/approve_students")
@login_required
def approve_students():
    with get_connection() as conn:
        pending_students = conn.execute("""
            SELECT sa.admission_no, sa.is_approved, s.name, s.batch 
            FROM students_auth sa
            JOIN students s ON sa.admission_no = s.admission_no
            WHERE sa.is_approved = 0
            ORDER BY s.batch, s.name
        """).fetchall()
    
    return render_template("approve_students.html", pending_students=pending_students)

@app.route("/approve_student/<admission_no>")
@login_required
def approve_student_action(admission_no):
    try:
        with get_connection() as conn:
            # Only update the approval status, as the student record is already created.
            conn.execute("UPDATE students_auth SET is_approved = 1 WHERE admission_no = ?", (admission_no,))
        flash(f"Student {admission_no} approved successfully! They can now log in.", 'success')
    except Exception as e:
        flash(f"Error approving student: {str(e)}", 'danger')
        
    return redirect(url_for('approve_students'))


@app.route("/reject_student/<admission_no>")
@login_required
def reject_student_action(admission_no):
    """
    Deletes a student's profile and their pending portal registration.
    This action ensures that the student must re-register if they wish to try again.
    """
    try:
        with get_connection() as conn:
            # 1. Get the student's ID for deletion, needed to ensure the flash message is accurate.
            student = conn.execute("SELECT name, id FROM students WHERE admission_no = ?", (admission_no,)).fetchone()
            
            if not student:
                flash(f"Error: Student with admission number {admission_no} not found or already deleted.", 'danger')
                return redirect(url_for('approve_students'))
                
            # 2. Deleting from 'students' cascades the deletion to 'students_auth' 
            # (and 'transactions', though no active transactions should exist for a pending user).
            conn.execute("DELETE FROM students WHERE id=?", (student['id'],))
            
        flash(f"Student account for {admission_no} ({student['name']}) rejected and deleted successfully.", 'success')
    except Exception as e:
        flash(f"Error rejecting student: {str(e)}", 'danger')
        
    return redirect(url_for('approve_students'))


# ----------------- BOOKS -----------------

@app.route("/add_book", methods=["GET", "POST"])
@login_required 
def add_book():
    if request.method == "POST":
        custom_id = request.form.get("custom_id")
        if custom_id and custom_id.strip() == "":
            custom_id = None
        elif custom_id:
            custom_id = custom_id.strip().upper()
        
        name = request.form["name"].strip()
        author = request.form["author"].strip()
        
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
@login_required 
def view_books():
    # This route now just renders the page shell.
    # The actual data will be loaded via JavaScript from the /api/view_books route.
    return render_template("view_books.html")


@app.route("/delete_book/<int:id>", methods=["POST"])
@login_required 
def delete_book(id):
    try:
        with get_connection() as conn:
            book = conn.execute("SELECT available, name FROM books WHERE id=?", (id,)).fetchone()
            if not book:
                  flash("Book not found.", "danger")
                  return redirect(url_for("view_books"))

            if not book['available']:
                flash(f"Cannot delete '{book['name']}'. It is currently issued out!", "danger")
                return redirect(url_for("view_books"))
                
            conn.execute("DELETE FROM books WHERE id=?", (id,))
        flash("Book deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting book: {str(e)}", "danger")
    return redirect(url_for("view_books"))

@app.route("/edit_book/<int:id>", methods=["GET", "POST"])
@login_required 
def edit_book(id):
    with get_connection() as conn:
        book = conn.execute("SELECT * FROM books WHERE id=?", (id,)).fetchone()
        
    if book is None:
        flash("Book not found!", "danger")
        return redirect(url_for("view_books"))

    if request.method == "POST":
        custom_id = request.form.get("custom_id")
        if custom_id and custom_id.strip() == "":
            custom_id = None
        elif custom_id:
            custom_id = custom_id.strip().upper()
            
        name = request.form["name"].strip()
        author = request.form["author"].strip()

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
            with get_connection() as conn:
                book = conn.execute("SELECT * FROM books WHERE id=?", (id,)).fetchone()
        except Exception as e:
            flash(f"Error updating book: {str(e)}", "danger")
            with get_connection() as conn:
                book = conn.execute("SELECT * FROM books WHERE id=?", (id,)).fetchone()

    return render_template("edit_book.html", book=book)

# ----------------- STUDENTS -----------------

@app.route("/add_student", methods=["GET", "POST"])
@login_required 
def add_student():
    if request.method == "POST":
        admission_no = request.form["admission_no"].strip().upper()
        name = request.form["name"].strip()
        batch = request.form["batch"]
        password = request.form["password"] # New field
        
        try:
            with get_connection() as conn:
                # 1. Create the student profile
                conn.execute("INSERT INTO students (admission_no, name, batch) VALUES (?, ?, ?)",
                             (admission_no, name, batch))
                
                # 2. Hash the password and create the approved authentication record
                hashed_pass = hash_password(password)
                conn.execute("INSERT INTO students_auth (admission_no, password_hash, is_approved) VALUES (?, ?, 1)",
                             (admission_no, hashed_pass))
                             
            flash("Student profile and portal account created successfully! They can now log in.", "success")
            return redirect(url_for('add_student'))
            
        except sqlite3.IntegrityError:
            flash(f"Student with Admission No '{admission_no}' already exists!", "danger")
        except Exception as e:
            flash(f"Error adding student: {str(e)}", "danger")
            
        return redirect(url_for("add_student"))
        
    return render_template("add_student.html")


@app.route("/view_students")
@login_required 
def view_students():
    # This route now just renders the page shell and fetches batches for the filter.
    with get_connection() as conn:
        batches = conn.execute("SELECT DISTINCT batch FROM students ORDER BY batch ASC").fetchall()
        
    return render_template("view_students.html", batches=batches)

@app.route("/api/view_students")
@login_required
def api_view_students():
    STUDENTS_PER_PAGE = 15
    page = request.args.get('page', 1, type=int)
    query = request.args.get('query', '')
    batch_filter = request.args.get('batch', 'all')
    status_filter = request.args.get('status', 'all')

    base_sql = "FROM students s LEFT JOIN students_auth sa ON s.admission_no = sa.admission_no"
    count_sql = "SELECT COUNT(s.id) "
    select_sql = "SELECT s.id, s.admission_no, s.name, s.batch, sa.is_approved "
    
    params = []
    conditions = []

    if query:
        search_term = f"%{query}%"
        conditions.append("(s.name LIKE ? OR s.admission_no LIKE ?)")
        params.extend([search_term, search_term])
        
    if batch_filter != 'all':
        conditions.append("s.batch = ?")
        params.append(batch_filter)

    if status_filter == 'approved':
        conditions.append("sa.is_approved = 1")
    elif status_filter == 'pending':
        conditions.append("(sa.is_approved = 0 OR sa.is_approved IS NULL)")

    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)
        base_sql += where_clause
    
    with get_connection() as conn:
        full_count_sql = count_sql + base_sql
        total_students = conn.execute(full_count_sql, tuple(params)).fetchone()[0]
        
        total_pages = 1
        if total_students > 0:
            total_pages = math.ceil(total_students / STUDENTS_PER_PAGE)

        if page > total_pages and total_pages > 0: page = total_pages
        if page < 1: page = 1

        offset = (page - 1) * STUDENTS_PER_PAGE
        
        paginated_sql = select_sql + base_sql + " ORDER BY s.name ASC LIMIT ? OFFSET ?"
        final_params = params + [STUDENTS_PER_PAGE, offset]
        
        students_data = conn.execute(paginated_sql, tuple(final_params)).fetchall()
        students = [dict(row) for row in students_data]
        
    return jsonify({
        'students': students,
        'pagination': {
            'page': page,
            'total_pages': total_pages,
            'total_students': total_students,
            'per_page': STUDENTS_PER_PAGE
        }
    })

@app.route("/delete_student/<int:id>", methods=["POST"])
@login_required 
def delete_student(id):
    try:
        with get_connection() as conn:
            active_issues = conn.execute("SELECT COUNT(id) FROM transactions WHERE student_id=? AND return_date IS NULL", (id,)).fetchone()[0]
            student = conn.execute("SELECT name, admission_no FROM students WHERE id=?", (id,)).fetchone()
            
            if not student:
                  flash("Student not found.", "danger")
                  return redirect(url_for("view_students"))

            if active_issues > 0:
                flash(f"Cannot delete student '{student['name']}'. They currently have {active_issues} book(s) issued!", "danger")
                return redirect(url_for("view_students"))
            
            # Deleting the student record will cascade and remove the auth record and transactions.
            conn.execute("DELETE FROM students WHERE id=?", (id,))
        flash("Student and their associated portal account deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting student: {str(e)}", "danger")
    return redirect(url_for("view_students"))

@app.route("/edit_student/<int:id>", methods=["GET", "POST"])
@login_required 
def edit_student(id):
    with get_connection() as conn:
        student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()
        
    if student is None:
        flash("Student not found!", "danger")
        return redirect(url_for("view_students"))

    if request.method == "POST":
        # old_admission_no = student['admission_no'] # Not explicitly needed due to foreign key cascade update logic
        new_admission_no = request.form["admission_no"].strip().upper()
        name = request.form["name"].strip()
        batch = request.form["batch"]

        try:
            with get_connection() as conn:
                # Update main student record. CASCADE handles the auth table update.
                conn.execute(
                    "UPDATE students SET admission_no=?, name=?, batch=? WHERE id=?",
                    (new_admission_no, name, batch, id)
                )

            flash(f"Student '{name}' updated successfully!", "success")
            return redirect(url_for("view_students"))
        except sqlite3.IntegrityError:
            flash("Student with this Admission No already exists!", "danger")
            with get_connection() as conn:
                student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()
        except Exception as e:
            flash(f"Error updating student: {str(e)}", "danger")
            with get_connection() as conn:
                student = conn.execute("SELECT * FROM students WHERE id=?", (id,)).fetchone()

    return render_template("edit_student.html", student=student)

# ----------------- TRANSACTIONS -----------------

@app.route("/issue", methods=["GET", "POST"])
@login_required 
def issue_book():
    if request.method == "POST":
        book_id_input = request.form["book_id"].strip()
        student_adm = request.form["admission_no"].strip().upper()
        loan_period_days = request.form.get("loan_period")
        custom_due_date_str = request.form.get("custom_due_date")
        
        issue_date_obj = date.today()
        calculated_due_date = ""

        if loan_period_days == "custom" and custom_due_date_str:
            try:
                calculated_due_date = datetime.datetime.strptime(custom_due_date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
                if datetime.datetime.strptime(calculated_due_date, '%Y-%m-%d').date() <= issue_date_obj:
                    flash("Custom Due Date must be after the Issue Date.", "danger")
                    return redirect(url_for("issue_book"))
            except ValueError:
                flash("Invalid Custom Due Date format.", "danger")
                return redirect(url_for("issue_book"))
        elif loan_period_days and loan_period_days != "custom":
            try:
                days = int(loan_period_days)
                calculated_due_date = (issue_date_obj + timedelta(days=days)).strftime('%Y-%m-%d')
            except ValueError:
                flash("Invalid Loan Period selected.", "danger")
                return redirect(url_for("issue_book"))
        else:
            flash("Please select a valid loan period or custom due date.", "danger")
            return redirect(url_for("issue_book"))
        
        with get_connection() as conn:
            # --- THIS IS THE CORRECTED LINE ---
            # It now checks for the uppercased custom_id OR the numeric id.
            book = conn.execute("SELECT * FROM books WHERE custom_id=? OR id=?", 
                                (book_id_input.upper(), book_id_input)).fetchone()
            
            student = conn.execute("SELECT * FROM students WHERE admission_no=?", (student_adm,)).fetchone()
            
            if not book:
                flash("Book not found! (Check ID or Custom ID)", "danger")
                return redirect(url_for("issue_book"))
            if not student:
                flash("Student not found! (Check Admission No)", "danger")
                return redirect(url_for("issue_book"))
            if not book["available"]:
                flash(f"Book '{book['name']}' is currently not available!", "danger")
                return redirect(url_for("issue_book"))
            
            try:
                conn.execute("INSERT INTO transactions (book_id, student_id, issue_date, due_date) VALUES (?, ?, ?, ?)",
                             (book["id"], student["id"], issue_date_obj.strftime('%Y-%m-%d'), calculated_due_date))
                conn.execute("UPDATE books SET available=0 WHERE id=?", (book["id"],))
                flash(f"Book '{book['name']}' issued to {student['name']}! Due Date: {calculated_due_date}", "success")
            except Exception as e:
                flash(f"Error issuing book: {str(e)}", "danger")
                
        return redirect(url_for("issue_book"))
    return render_template("issue.html")

@app.route("/return", methods=["GET", "POST"])
@login_required 
def return_book():
    if request.method == "POST":
        book_id_input = request.form["book_id"].strip()
        student_adm = request.form["admission_no"].strip().upper()
        
        with get_connection() as conn:
            # --- THIS IS THE CORRECTED LINE ---
            # It now checks for the uppercased custom_id OR the numeric id.
            book = conn.execute("SELECT * FROM books WHERE custom_id=? OR id=?", 
                                (book_id_input.upper(), book_id_input)).fetchone()
            
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

@app.route("/extend/<int:transaction_id>", methods=["POST"])
@login_required
def extend_loan(transaction_id):
    # Fetch the transaction to ensure it exists and to get the current due date
    with get_connection() as conn:
        transaction = conn.execute(
            "SELECT due_date FROM transactions WHERE id = ? AND return_date IS NULL",
            (transaction_id,)
        ).fetchone()

    if not transaction:
        flash("Active transaction not found or already returned.", "danger")
        return redirect(url_for("active_issues"))

    new_due_date_str = request.form.get("new_due_date")
    
    try:
        new_due_date_obj = datetime.datetime.strptime(new_due_date_str, '%Y-%m-%d').date()
        current_due_date_obj = datetime.datetime.strptime(transaction['due_date'], '%Y-%m-%d').date()
        
        # Validation checks
        if new_due_date_obj <= current_due_date_obj:
            flash("New due date must be *after* the current due date.", "danger")
        elif new_due_date_obj <= date.today():
             flash("New due date must be in the future.", "danger")
        else:
            # Update the database if validation passes
            with get_connection() as conn_update:
                conn_update.execute("UPDATE transactions SET due_date=? WHERE id=?", 
                                     (new_due_date_str, transaction_id))
            flash(f"Loan for transaction #{transaction_id} extended successfully! New Due Date: {new_due_date_str}", "success")
            
    except ValueError:
        flash("Invalid date format provided.", "danger")
    except Exception as e:
        flash(f"Error extending loan: {str(e)}", "danger")

    return redirect(url_for("active_issues"))

@app.route("/active_issues")
@login_required 
def active_issues():
    with get_connection() as conn:
        transactions = conn.execute("""SELECT t.id, t.student_id, t.issue_date, t.due_date, 
                                           COALESCE(b.name, '[DELETED BOOK]') AS book_name, 
                                           COALESCE(s.name, '[DELETED STUDENT]') AS student_name, 
                                           COALESCE(s.admission_no, 'N/A') AS admission_no,
                                           COALESCE(s.batch, '-') AS batch
                                           FROM transactions t
                                           LEFT JOIN books b ON t.book_id = b.id
                                           LEFT JOIN students s ON t.student_id = s.id
                                           WHERE t.return_date IS NULL
                                           ORDER BY t.due_date ASC""").fetchall() 
    
    today_str = date.today().strftime('%Y-%m-%d')
    transactions_list = []
    
    for t in transactions:
        t_dict = dict(t)
        t_dict['is_overdue'] = t_dict['due_date'] < today_str
        transactions_list.append(t_dict)
        
    return render_template("active_issues.html", transactions=transactions_list)

@app.route("/transaction_history")
@login_required 
def transaction_history():
    query = request.args.get('query', '')
    status_filter = request.args.get('status', 'all')
    
    sql = """
        SELECT t.id, 
               COALESCE(b.name, '[DELETED BOOK]') AS book_name, 
               COALESCE(s.name, '[DELETED STUDENT]') AS student_name, 
               COALESCE(s.admission_no, 'N/A') AS admission_no,
               COALESCE(s.batch, '-') AS batch,
               t.issue_date, 
               t.return_date
        FROM transactions t
        LEFT JOIN books b ON t.book_id = b.id
        LEFT JOIN students s ON t.student_id = s.id
    """
    params = []
    conditions = []

    if query:
        search_term = f"%{query}%"
        conditions.append("(b.name LIKE ? OR s.name LIKE ? OR s.admission_no LIKE ?)")
        params.extend([search_term, search_term, search_term])
        
    if status_filter == 'active':
        conditions.append("t.return_date IS NULL")
    elif status_filter == 'returned':
        conditions.append("t.return_date IS NOT NULL")

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
        
    sql += " ORDER BY t.id DESC"

    with get_connection() as conn:
        transactions = conn.execute(sql, tuple(params)).fetchall()
        
    return render_template("transaction_history.html", 
                           transactions=transactions,
                           search_query=query,
                           current_status=status_filter)

@app.route("/search_books", methods=["GET", "POST"])
@login_required 
def search_books():
    results = []
    if request.method == "POST":
        query = request.form["query"].strip()
        with get_connection() as conn:
            search_term = f"%{query}%"
            results = conn.execute("""SELECT * FROM books 
                                           WHERE name LIKE ? 
                                           OR author LIKE ?
                                           OR custom_id LIKE ?
                                           OR id LIKE ?
                                           ORDER BY name ASC""",
                                           (search_term, search_term, search_term, search_term)).fetchall()
    return render_template("search_books.html", results=results)

# ----------------- AJAX ENDPOINTS (Unchanged) -----------------

@app.route("/lookup_book/<book_id>")
def lookup_book(book_id):
    if not book_id:
        return jsonify({"name": "Book not found", "available": False}), 404
        
    with get_connection() as conn:
        # Query by either the primary key (id) or the custom_id
        book = conn.execute("SELECT name, available FROM books WHERE id = ? OR custom_id = ?", 
                            (book_id, book_id.upper())).fetchone()
    
    if book:
        # The column names are 'name' and 'available'
        return jsonify({"name": book["name"], "available": bool(book["available"])})
    else:
        return jsonify({"name": "Book not found", "available": False}), 404


@app.route("/lookup_student/<admission_no>")
def lookup_student(admission_no):
    admission_no = admission_no.strip().upper()
    if not admission_no:
           return jsonify({'name': ''}), 404
           
    with get_connection() as conn:
        student = conn.execute("SELECT name FROM students WHERE admission_no=?", (admission_no,)).fetchone()
    
    if student:
        return jsonify({'name': student["name"]}), 200
    
    return jsonify({'name': 'Student not found.'}), 404

@app.route("/reset_student_password/<int:id>", methods=["POST"])
@login_required
def reset_student_password(id):
    with get_connection() as conn:
        student = conn.execute("SELECT admission_no, name FROM students WHERE id = ?", (id,)).fetchone()

    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for('view_students'))

    new_password = request.form.get('new_password')
    if not new_password:
        flash("Password cannot be empty.", "danger")
        return redirect(url_for('view_students'))

    try:
        hashed_pass = hash_password(new_password)
        with get_connection() as conn_update:
            conn_update.execute("UPDATE students_auth SET password_hash = ? WHERE admission_no = ?", 
                                (hashed_pass, student['admission_no']))
        flash(f"Password for {student['name']} has been updated successfully.", "success")
    except Exception as e:
        flash(f"An error occurred while resetting the password: {str(e)}", "danger")

    return redirect(url_for('view_students'))

@app.context_processor
def inject_pending_count():
    """Injects the count of pending student approvals into all templates."""
    with get_connection() as conn:
        try:
            count = conn.execute("SELECT COUNT(id) FROM students_auth WHERE is_approved = 0").fetchone()[0]
            return dict(pending_count=count)
        except:
            return dict(pending_count=0)

@app.route("/api/view_books")
@login_required
def api_view_books():
    BOOKS_PER_PAGE = 15
    page = request.args.get('page', 1, type=int)
    query = request.args.get('query', '')
    availability_filter = request.args.get('filter', 'all')
    
    base_sql = "FROM books"
    count_sql = "SELECT COUNT(id) "
    select_sql = "SELECT * "
    params = []
    
    conditions = []
    if query:
        search_term = f"%{query}%"
        conditions.append("(name LIKE ? OR author LIKE ? OR custom_id LIKE ?)")
        params.extend([search_term, search_term, search_term])
        
    if availability_filter == 'available':
        conditions.append("available = 1")
    elif availability_filter == 'issued':
        conditions.append("available = 0")
        
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)
        base_sql += where_clause
    
    with get_connection() as conn:
        full_count_sql = count_sql + base_sql
        total_books = conn.execute(full_count_sql, tuple(params)).fetchone()[0]
        
        total_pages = 1
        if total_books > 0:
            total_pages = math.ceil(total_books / BOOKS_PER_PAGE)

        if page > total_pages and total_pages > 0:
            page = total_pages
        if page < 1:
            page = 1

        offset = (page - 1) * BOOKS_PER_PAGE
        
        paginated_sql = select_sql + base_sql + " ORDER BY name ASC LIMIT ? OFFSET ?"
        final_params = params + [BOOKS_PER_PAGE, offset]
        
        books_data = conn.execute(paginated_sql, tuple(final_params)).fetchall()
        books = [dict(row) for row in books_data]
        
    return jsonify({
        'books': books,
        'pagination': {
            'page': page,
            'total_pages': total_pages,
            'total_books': total_books,
            'per_page': BOOKS_PER_PAGE
        }
    })

@app.route('/student_change_password', methods=['GET', 'POST'])
@student_login_required
def student_change_password():
    student_adm_no = session.get('student_adm_no')
    student_info = None
    with get_connection() as conn:
        student_info = conn.execute("SELECT name, batch FROM students WHERE admission_no=?", (student_adm_no,)).fetchone()

    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            flash("New passwords do not match.", 'danger')
            return redirect(url_for('student_change_password'))

        with get_connection() as conn:
            user = conn.execute("SELECT password_hash FROM students_auth WHERE admission_no = ?", (student_adm_no,)).fetchone()
            
            if user and check_password(user['password_hash'], current_password):
                try:
                    new_hashed_password = hash_password(new_password)
                    conn.execute("UPDATE students_auth SET password_hash = ? WHERE admission_no = ?", 
                                 (new_hashed_password, student_adm_no))
                    flash("Your password has been updated successfully!", 'success')
                    return redirect(url_for('student_dashboard'))
                except Exception as e:
                    flash(f"An error occurred while updating your password: {str(e)}", "danger")
            else:
                flash("Your current password was incorrect. Please try again.", 'danger')

    return render_template('student_change_password.html', student_info=student_info)

@app.route("/student_details/<int:id>")
@login_required
def student_details(id):
    with get_connection() as conn:
        # 1. Get Student's basic info
        student = conn.execute("SELECT * FROM students WHERE id = ?", (id,)).fetchone()
        
        if not student:
            flash("Student not found.", "danger")
            return redirect(url_for('view_students'))

        # 2. Get Student's active loans
        active_loans_data = conn.execute("""
            SELECT b.name as book_name, t.issue_date, t.due_date
            FROM transactions t
            JOIN books b ON t.book_id = b.id
            WHERE t.student_id = ? AND t.return_date IS NULL
            ORDER BY t.due_date ASC
        """, (id,)).fetchall()
        
        # Add overdue status in Python
        today_str = date.today().strftime('%Y-%m-%d')
        active_loans = []
        for loan in active_loans_data:
            loan_dict = dict(loan)
            loan_dict['is_overdue'] = loan_dict['due_date'] < today_str
            active_loans.append(loan_dict)

        # 3. Get Student's loan history (returned books)
        loan_history = conn.execute("""
            SELECT b.name as book_name, t.issue_date, t.return_date
            FROM transactions t
            JOIN books b ON t.book_id = b.id
            WHERE t.student_id = ? AND t.return_date IS NOT NULL
            ORDER BY t.return_date DESC
        """, (id,)).fetchall()

    return render_template("student_details.html", 
                           student=student, 
                           active_loans=active_loans, 
                           loan_history=loan_history)

@app.route("/api/student_search")
@student_login_required
def api_student_search():
    BOOKS_PER_PAGE = 15
    page = request.args.get('page', 1, type=int)
    query = request.args.get('query', '')
    status_filter = request.args.get('status', 'all')

    params = []
    conditions = []
    
    if query:
        search_term = f"%{query}%"
        conditions.append("(name LIKE ? OR author LIKE ? OR custom_id LIKE ?)")
        params.extend([search_term, search_term, search_term])
        
    if status_filter == 'available':
        conditions.append("available = 1")
    elif status_filter == 'issued':
        conditions.append("available = 0")

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)
    
    with get_connection() as conn:
        # First, get the total count of books MATCHING THE FILTERS
        count_sql = "SELECT COUNT(id) FROM books" + where_clause
        total_books = conn.execute(count_sql, tuple(params)).fetchone()[0]
        
        # Calculate total pages
        total_pages = 1
        if total_books > 0:
            total_pages = math.ceil(total_books / BOOKS_PER_PAGE)

        if page > total_pages and total_pages > 0: page = total_pages
        if page < 1: page = 1

        offset = (page - 1) * BOOKS_PER_PAGE
        
        # Prepare the final query to get just one page of books
        select_sql = "SELECT * FROM books" + where_clause + " ORDER BY name ASC LIMIT ? OFFSET ?"
        final_params = params + [BOOKS_PER_PAGE, offset]
        
        books_data = conn.execute(select_sql, tuple(final_params)).fetchall()
        books = [dict(row) for row in books_data]
        
    return jsonify({
        'books': books,
        'pagination': {
            'page': page,
            'total_pages': total_pages,
            'total_books': total_books,
            'per_page': BOOKS_PER_PAGE
        }
    })

if __name__ == "__main__":
    app.run(debug=True)
