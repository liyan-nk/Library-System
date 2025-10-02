# 📚 Library Management System

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-2.0+-lightgrey?logo=flask)
![SQLite](https://img.shields.io/badge/SQLite-Database-blue?logo=sqlite)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-Frontend-38B2AC?logo=tailwind-css)
![License](https://img.shields.io/badge/License-MIT-green)
![PWA](https://img.shields.io/badge/PWA-Supported-orange?logo=pwa)

A comprehensive, **full-stack web application** for managing a library, built with **Flask** and **SQLite**.  
This project provides a **dual-portal system** (Librarian + Student), real-time data handling, analytics, and a fully responsive, installable **Progressive Web App (PWA)** for students.

---

## 🌐 Live Demo
🔗 **[Try the Live Application](https://library-system-demo.onrender.com/)**  

> ⚠️ Note: Free hosting may take up to a minute to wake up if inactive.  
> Database is temporary on this free tier and resets after inactivity.

---

## 🚀 Features

### 🧑‍💻 Librarian Portal
A powerful dashboard for complete library management:
- 📊 **Analytics Dashboard**: Live stats on books, students, and loans with *Top Readers* and *Most Borrowed Books* charts.  
- 🔎 **Dynamic Data Management**: AJAX-powered searching, filtering, and pagination (no reloads).  
- 📝 **On-Page Modals**: Add, edit, delete, and reset data without leaving the page.  
- 🔄 **Loan Cycle Management**: Issue, return, and extend book loans seamlessly.  
- ✅ **Student Approval System**: Approve/reject student registrations with live notification badges.  

### 🎓 Student Portal
A clean, responsive, mobile-first portal:
- 📱 **PWA Support**: Installable on iOS/Android with offline capability.  
- 🧑 **Personalized Dashboard**: Active loans, loan history, and leaderboard with self-highlight.  
- 📚 **Browse & Search**: AJAX-powered book search and availability filters.  
- 🔐 **Self-Service**: Students can self-register (pending approval) and manage passwords.  

---

## 🛠️ Tech Stack

- **Backend**: [Flask](https://flask.palletsprojects.com/) (Python)  
- **Database**: [SQLite](https://www.sqlite.org/)  
- **Frontend**: [Tailwind CSS](https://tailwindcss.com/)  
- **Dynamic Features**: JavaScript (AJAX, [Chart.js](https://www.chartjs.org/))  
- **Data Import**: [Pandas](https://pandas.pydata.org/) for bulk Excel uploads  

---

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/liyan-nk/Library-System
cd Library-System
````

### 2. Create a Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
python app.py
```

The app will be available at: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**
A `library.db` file will be created automatically.

---

## 🔑 Default Credentials

* **Librarian Username**: `librarian`
* **Librarian Password**: `password`

---

## 📂 Bulk Import Data (Optional)

### Import Books

1. Create `books_data.xlsx` with columns:
   `name, author, custom_id`
2. Run:

   ```bash
   python import_books.py
   ```

### Import Students

1. Create `students_data.xlsx` with columns:
   `admission_no, name, batch, password`
2. Run:

   ```bash
   python import_students.py
   ```

---

## 📦 Folder Structure

```
Library-Management-System/
│── app.py                 # Main Flask app
│── library.db             # SQLite database (auto-generated)
│── requirements.txt       # Python dependencies
│── templates/             # HTML templates (Flask Jinja2)
│── static/                # CSS, JS, images
│── import_books.py        # Bulk import script for books
│── import_students.py     # Bulk import script for students
│── README.md              # Project documentation
```

---

## 🛡️ License

This project is licensed under the **MIT License**.
You are free to use, modify, and distribute with attribution.

---

## 💡 Future Improvements

* 🔔 Email notifications for overdue books
* 📥 Export reports (PDF/Excel)
* 🌍 Multi-language support
* 🖼️ Richer student profiles

---

## 🤝 Contributing

Contributions are welcome!
Fork the repo and submit a PR, or open an issue to suggest improvements.

---

## ✨ Acknowledgements

* [Flask](https://flask.palletsprojects.com/)
* [Tailwind CSS](https://tailwindcss.com/)
* [Chart.js](https://www.chartjs.org/)
* [Pandas](https://pandas.pydata.org/)

---
