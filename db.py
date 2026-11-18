"""CAMPUS//OS - MySQL connection helpers, 6-table schema and the demo seed."""

import os
import random
from datetime import date, timedelta

import mysql.connector
from mysql.connector import Error

HOST, USER, PASSWORD, DATABASE = "localhost", "root", "root", "campus_os"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS students (id INT AUTO_INCREMENT PRIMARY KEY,
        admission_no VARCHAR(20) NOT NULL UNIQUE, name VARCHAR(80) NOT NULL,
        class_name VARCHAR(10) NOT NULL, section CHAR(1) NOT NULL,
        guardian VARCHAR(80) DEFAULT '', phone VARCHAR(20) DEFAULT '',
        source VARCHAR(10) DEFAULT 'real')""",
    """CREATE TABLE IF NOT EXISTS attendance (id BIGINT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL, day DATE NOT NULL, status CHAR(1) NOT NULL,
        UNIQUE KEY one_per_day (student_id, day),
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE)""",
    """CREATE TABLE IF NOT EXISTS books (id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(120) NOT NULL, author VARCHAR(80) DEFAULT '',
        category VARCHAR(40) DEFAULT 'General',
        copies_total INT NOT NULL DEFAULT 1, copies_available INT NOT NULL DEFAULT 1)""",
    """CREATE TABLE IF NOT EXISTS loans (id INT AUTO_INCREMENT PRIMARY KEY,
        book_id INT NOT NULL, student_id INT NOT NULL, issued_on DATE NOT NULL,
        due_on DATE NOT NULL, returned_on DATE NULL,
        FOREIGN KEY (book_id) REFERENCES books(id),
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE)""",
    """CREATE TABLE IF NOT EXISTS issues (id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(120) NOT NULL, category VARCHAR(30) NOT NULL,
        location VARCHAR(40) DEFAULT '', priority VARCHAR(10) NOT NULL DEFAULT 'MEDIUM',
        status VARCHAR(12) NOT NULL DEFAULT 'OPEN', raised_on DATE NOT NULL,
        closed_on DATE NULL, raised_by VARCHAR(60) DEFAULT 'operator')""",
    """CREATE TABLE IF NOT EXISTS activity (id INT AUTO_INCREMENT PRIMARY KEY,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP, action VARCHAR(40) NOT NULL,
        detail VARCHAR(160) DEFAULT '')""",
]

NAMES = ["Aarav Sharma", "Diya Patel", "Kabir Nair", "Ananya Rao", "Ishaan Verma",
         "Meera Iyer", "Rohan Gupta", "Sara Khan", "Vivaan Joshi", "Aditi Menon",
         "Arjun Reddy", "Nisha Bose", "Dev Malhotra", "Riya Chawla", "Karan Pillai",
         "Tanvi Desai", "Neel Kapoor", "Pooja Shetty", "Yash Thakur", "Ira Singh",
         "Manav Bansal", "Sneha Kulkarni", "Om Prakash", "Zoya Ahmed"]

BOOKS = [("Concepts of Physics", "H.C. Verma", "Science", 6),
         ("NCERT Mathematics IX", "NCERT", "Mathematics", 8),
         ("Wings of Fire", "A.P.J. Abdul Kalam", "Biography", 4),
         ("The Diary of a Young Girl", "Anne Frank", "Biography", 3),
         ("Oxford School Atlas", "Oxford", "Reference", 2),
         ("Objective Biology", "Trueman", "Science", 5),
         ("Indian Constitution", "P.M. Bakshi", "Civics", 3),
         ("Oxford School Dictionary", "Oxford", "Reference", 6),
         ("Panchatantra Tales", "Vishnu Sharma", "Fiction", 4),
         ("Chemistry Lab Manual", "Laxmi", "Science", 7),
         ("Computer Science with Python", "Preeti Arora", "Computer", 5),
         ("Cricket: Making of a Champion", "R. Sharma", "Sports", 2)]

ISSUES = [("Projector dead in Lab 2", "ELECTRICAL", "Lab 2", "CRITICAL", "OPEN", 11),
          ("Broken bench in 8-B", "FURNITURE", "Room 8-B", "MEDIUM", "OPEN", 3),
          ("Water cooler leaking", "PLUMBING", "Corridor A", "HIGH", "OPEN", 9),
          ("Fan noise in library", "ELECTRICAL", "Library", "LOW", "OPEN", 2),
          ("Whiteboard stained", "FURNITURE", "Room 9-A", "LOW", "RESOLVED", 14),
          ("Cricket net torn", "SPORTS", "Ground", "MEDIUM", "OPEN", 6),
          ("Computer 4 will not boot", "COMPUTER", "Computer Lab", "HIGH", "OPEN", 8),
          ("Washroom tap broken", "PLUMBING", "Block B", "MEDIUM", "RESOLVED", 12),
          ("Fire extinguisher expired", "SAFETY", "Block A", "CRITICAL", "OPEN", 10),
          ("Classroom door lock jammed", "FURNITURE", "Room 9-A", "HIGH", "OPEN", 5)]


def connect(with_db=True):
    try:
        return mysql.connector.connect(host=HOST, user=USER, password=PASSWORD,
                                       database=DATABASE if with_db else None)
    except Error as exc:
        raise SystemExit(f"MYSQL OFFLINE: {exc}\nStart MySQL80, then check the details in db.py")


def rows(sql, args=()):
    """Run a SELECT and return a list of dicts; never raises into the UI."""
    try:
        conn = connect()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, args)
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return data
    except Error as exc:
        print(f"[SQL ERROR] {exc}")
        return []


def one(sql, args=()):
    found = rows(sql, args)
    return found[0] if found else {}


def run(sql, args=()):
    """INSERT / UPDATE / DELETE in a transaction, rolled back on error."""
    conn = connect()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, args)
        conn.commit()
        return cursor.lastrowid or cursor.rowcount
    except Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_schema(reset=False):
    """Create the database and tables. reset=True drops every existing table first."""
    admin = connect(with_db=False)
    admin.cursor().execute(f"CREATE DATABASE IF NOT EXISTS {DATABASE}")
    admin.commit()
    admin.close()
    conn = connect()
    cursor = conn.cursor()
    if reset:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (DATABASE,))
        for (table,) in cursor.fetchall():
            cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    for statement in SCHEMA:
        cursor.execute(statement)
    conn.commit()
    cursor.close()
    conn.close()
    for folder in ("exports", "backups", "imports"):
        os.makedirs(os.path.join(DATA, folder), exist_ok=True)


def purge_demo():
    """Delete seeded students; attendance and loans follow via ON DELETE CASCADE."""
    return run("DELETE FROM students WHERE source = 'demo'")


def seed_demo(reset=True):
    """Load a small but realistic campus: 24 students, 10 school days, loans, issues."""
    create_schema(reset)
    rnd = random.Random(7)
    conn = connect()
    cur = conn.cursor()
    people = []
    for index, name in enumerate(NAMES):
        klass, section = ("8", "A") if index < 8 else ("8", "B") if index < 16 else ("9", "A")
        people.append((f"ADM{1000 + index}", name, klass, section,
                       "Mr. " + name.split()[-1], f"9810{index:06d}"))
    cur.executemany("INSERT INTO students (admission_no, name, class_name, section, guardian, "
                    "phone, source) VALUES (%s, %s, %s, %s, %s, %s, 'demo')", people)
    cur.execute("SELECT id FROM students ORDER BY id")
    ids = [row[0] for row in cur.fetchall()]

    days = [date.today() - timedelta(days=n) for n in range(1, 20)]
    days = [d for d in days if d.weekday() < 5][:10]
    marks = [(student_id, day, "P" if rnd.random() < 0.97 - (index % 7) * 0.04 else "A")
             for index, student_id in enumerate(ids) for day in days]
    cur.executemany("INSERT INTO attendance (student_id, day, status) VALUES (%s, %s, %s)", marks)

    cur.executemany("INSERT INTO books (title, author, category, copies_total, copies_available) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    [(t, a, c, n, n - (i % 3)) for i, (t, a, c, n) in enumerate(BOOKS)])
    cur.execute("SELECT id FROM books ORDER BY id")
    book_ids = [row[0] for row in cur.fetchall()]
    loans = []
    for i in range(8):
        issued = date.today() - timedelta(days=32 - i * 3)
        loans.append((book_ids[i], ids[(i * 3) % len(ids)], issued, issued + timedelta(days=14)))
    cur.executemany("INSERT INTO loans (book_id, student_id, issued_on, due_on) "
                    "VALUES (%s, %s, %s, %s)", loans)

    cur.executemany("INSERT INTO issues (title, category, location, priority, status, raised_on) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    [(t, c, loc, p, s, date.today() - timedelta(days=age))
                     for t, c, loc, p, s, age in ISSUES])
    cur.executemany("INSERT INTO activity (action, detail) VALUES (%s, %s)",
                    [("SEED_DEMO", "demo campus generated"), ("ISSUE_BOOK", "8 books issued"),
                     ("MARK_ATTENDANCE", f"{len(ids)} students"), ("IMPORT_CSV", "students.csv")])
    conn.commit()
    cur.close()
    conn.close()
    return {"students": len(ids), "attendance": len(marks), "books": len(book_ids)}
