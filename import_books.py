import pandas as pd
import sqlite3

# --- Configuration ---
EXCEL_FILE = 'books_data.xlsx'
DB_FILE = 'library.db'
TABLE_NAME = 'books'

def import_data():
    """Reads data from an Excel file and inserts it into the SQLite database."""
    try:
        # Read the Excel file into a pandas DataFrame
        df = pd.read_excel(EXCEL_FILE)
        print(f"Found {len(df)} records in the Excel file.")

        # Connect to the SQLite database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        books_added = 0
        books_skipped = 0
        for index, row in df.iterrows():
            # Skip rows with empty 'name' or 'author' to prevent errors and bad data
            if pd.isna(row.get('name')) or pd.isna(row.get('author')):
                books_skipped += 1
                continue

            book_name = str(row['name']).strip()
            author_name = str(row['author']).strip()

            # Handle potentially blank custom_id
            custom_id = row.get('custom_id')
            if pd.isna(custom_id):
                final_custom_id = None
            else:
                final_custom_id = str(custom_id).strip().upper()

            # --- FIX: ADDED A CHECK FOR DUPLICATE CUSTOM_ID ---
            if final_custom_id: # Only check if a custom_id is provided
                cursor.execute(f"SELECT id FROM {TABLE_NAME} WHERE custom_id = ?", (final_custom_id,))
                if cursor.fetchone():
                    print(f"Skipping record: Custom ID '{final_custom_id}' for book '{book_name}' already exists in the database.")
                    books_skipped += 1
                    continue
            
            # Check if a book with the same name and author already exists to avoid duplicates
            cursor.execute(f"SELECT id FROM {TABLE_NAME} WHERE name = ? AND author = ?", (book_name, author_name))
            if cursor.fetchone():
                print(f"Skipping duplicate book (by name/author): {book_name}")
                books_skipped += 1
                continue

            # Prepare the data for insertion
            book_data = (
                final_custom_id,
                book_name,
                author_name,
                1 # Set 'available' to True by default
            )
            
            # Insert the record into the database
            cursor.execute(f"INSERT INTO {TABLE_NAME} (custom_id, name, author, available) VALUES (?, ?, ?, ?)", book_data)
            books_added += 1

        # Commit the changes and close the connection
        conn.commit()
        conn.close()
        
        print("-" * 20)
        print(f"Success! Added {books_added} new books to the database.")
        if books_skipped > 0:
            print(f"Skipped {books_skipped} records (duplicates or empty rows).")

    except FileNotFoundError:
        print(f"Error: The file '{EXCEL_FILE}' was not found. Make sure it's in the same folder as this script.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    import_data()