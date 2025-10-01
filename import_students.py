import pandas as pd
import sqlite3
from app import hash_password # We'll reuse the hashing function from your app

# --- Configuration ---
EXCEL_FILE = 'students_data.xlsx'
DB_FILE = 'library.db'

def import_students():
    """Reads student data from an Excel file and inserts it into the database."""
    try:
        df = pd.read_excel(EXCEL_FILE)
        print(f"Found {len(df)} student records in the Excel file.")

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        students_added = 0
        students_skipped = 0
        for index, row in df.iterrows():
            # Basic validation to skip empty rows
            if pd.isna(row.get('admission_no')) or pd.isna(row.get('name')) or pd.isna(row.get('password')):
                students_skipped += 1
                continue

            # Clean and prepare data
            admission_no = str(row['admission_no']).strip().upper()
            name = str(row['name']).strip()
            batch = str(row['batch']).strip()
            password = str(row['password'])

            # Check if student with the same admission_no already exists
            cursor.execute("SELECT id FROM students WHERE admission_no = ?", (admission_no,))
            if cursor.fetchone():
                print(f"Skipping duplicate student: {name} ({admission_no})")
                students_skipped += 1
                continue

            # Hash the password from the Excel sheet
            hashed_pass = hash_password(password)
            
            # Insert into 'students' table
            cursor.execute("INSERT INTO students (admission_no, name, batch) VALUES (?, ?, ?)",
                           (admission_no, name, batch))
            
            # Insert into 'students_auth' table and set as approved (is_approved = 1)
            cursor.execute("INSERT INTO students_auth (admission_no, password_hash, is_approved) VALUES (?, ?, 1)",
                           (admission_no, hashed_pass))
            
            students_added += 1

        conn.commit()
        conn.close()
        
        print("-" * 20)
        print(f"Success! Added {students_added} new students to the database.")
        if students_skipped > 0:
            print(f"Skipped {students_skipped} records (duplicates or empty rows).")

    except FileNotFoundError:
        print(f"Error: The file '{EXCEL_FILE}' was not found. Make sure it's in the same folder as this script.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    import_students()