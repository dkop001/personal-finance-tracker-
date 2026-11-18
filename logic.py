"""CAMPUS//OS - every query, the insight rules, CSV handling and backups."""

import csv
import os
from datetime import date, timedelta

import db

TABLES = ("students", "attendance", "books", "loans", "issues", "activity")


def log(action, detail=""):
    db.run("INSERT INTO activity (action, detail) VALUES (%s, %s)", (action, str(detail)[:160]))


def stats():
    return db.one("""
        SELECT (SELECT COUNT(*) FROM students) AS students,
               COALESCE((SELECT ROUND(AVG(status = 'P') * 100, 1) FROM attendance), 0) AS attendance,
               (SELECT COUNT(*) FROM issues WHERE status <> 'RESOLVED') AS open_issues,
               (SELECT COUNT(*) FROM loans WHERE returned_on IS NULL) AS issued, (SELECT COUNT(*) FROM books) AS titles,
               (SELECT COALESCE(CONCAT(MIN(day), ' to ', MAX(day)), 'no records') FROM attendance) AS span""")


def attendance_by_class():
    return db.rows("""
        SELECT CONCAT(s.class_name, '-', s.section) AS label, COUNT(DISTINCT s.id) AS students,
               COALESCE(ROUND(AVG(a.status = 'P') * 100, 1), 0) AS pct
        FROM students s LEFT JOIN attendance a ON a.student_id = s.id
        GROUP BY label ORDER BY pct DESC""")


def at_risk():
    return db.rows("""
        SELECT s.admission_no, s.name, CONCAT(s.class_name, '-', s.section) AS cls,
               COUNT(a.id) AS days, ROUND(AVG(a.status = 'P') * 100, 1) AS pct
        FROM students s JOIN attendance a ON a.student_id = s.id
        GROUP BY s.id, s.admission_no, s.name, s.class_name, s.section
        HAVING pct < 75 ORDER BY pct ASC""")


def students(term=""):
    like = f"%{term.strip()}%"
    return db.rows("""
        SELECT s.admission_no, s.name, CONCAT(s.class_name, '-', s.section) AS cls, s.guardian,
               COALESCE(ROUND(AVG(a.status = 'P') * 100, 1), 0) AS pct
        FROM students s LEFT JOIN attendance a ON a.student_id = s.id
        WHERE s.name LIKE %s OR s.admission_no LIKE %s
        GROUP BY s.id, s.admission_no, s.name, s.class_name, s.section, s.guardian
        ORDER BY pct DESC, s.name LIMIT 100""", (like, like))


def add_student(fields):
    if not fields["name"] or not fields["admission_no"]:
        raise ValueError("admission number and name are required")
    db.run("""INSERT INTO students (admission_no, name, class_name, section, guardian, phone, source)
              VALUES (%s, %s, %s, %s, %s, %s, 'real')""",
           (fields["admission_no"], fields["name"], fields["class_name"] or "8",
            (fields["section"] or "A")[0], fields.get("guardian", ""), fields.get("phone", "")))
    log("ADD_STUDENT", fields["name"])


def books(term=""):
    like = f"%{term.strip()}%"
    return db.rows("""SELECT id, title, category, copies_total, copies_available FROM books
                      WHERE title LIKE %s OR category LIKE %s ORDER BY copies_available, title LIMIT 100""", (like, like))


def open_loans():
    return db.rows("""SELECT l.id, s.name, b.title, l.due_on FROM loans l
                      JOIN students s ON s.id = l.student_id JOIN books b ON b.id = l.book_id
                      WHERE l.returned_on IS NULL ORDER BY l.due_on""")


def overdue():
    return db.rows("""SELECT l.id, s.name, b.title, DATEDIFF(CURDATE(), l.due_on) AS days_late FROM loans l
                      JOIN students s ON s.id = l.student_id JOIN books b ON b.id = l.book_id
                      WHERE l.returned_on IS NULL AND l.due_on < CURDATE() ORDER BY days_late DESC""")


def issue_book(book_id, student_id):
    copy = db.one("SELECT copies_available FROM books WHERE id = %s", (book_id,))
    if not copy or copy["copies_available"] < 1:
        raise ValueError("that title has no copies available")
    db.run("UPDATE books SET copies_available = copies_available - 1 WHERE id = %s", (book_id,))
    db.run("INSERT INTO loans (book_id, student_id, issued_on, due_on) VALUES (%s, %s, %s, %s)",
           (book_id, student_id, date.today(), date.today() + timedelta(days=14)))
    log("ISSUE_BOOK", f"book {book_id} -> student {student_id}")


def return_loan(loan_id):
    loan = db.one("SELECT book_id FROM loans WHERE id = %s AND returned_on IS NULL", (loan_id,))
    if not loan:
        raise ValueError("no open loan with that id")
    db.run("UPDATE loans SET returned_on = CURDATE() WHERE id = %s", (loan_id,))
    db.run("UPDATE books SET copies_available = copies_available + 1 WHERE id = %s", (loan["book_id"],))
    log("RETURN_BOOK", f"loan {loan_id}")


def issues():
    return db.rows("""
        SELECT id, title, category, location, priority, status, DATEDIFF(CURDATE(), raised_on) AS age
        FROM issues
        ORDER BY status = 'RESOLVED', FIELD(priority, 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'), age DESC""")


def raise_issue(fields):
    if not fields["title"]:
        raise ValueError("a title is required")
    db.run("INSERT INTO issues (title, category, location, priority, raised_on) VALUES (%s, %s, %s, %s, CURDATE())",
           (fields["title"], fields.get("category") or "GENERAL", fields.get("location", ""),
            (fields.get("priority") or "MEDIUM").upper()))
    log("RAISE_ISSUE", fields["title"])


def close_issue(issue_id):
    if db.run("UPDATE issues SET status = 'RESOLVED', closed_on = CURDATE() WHERE id = %s", (issue_id,)) == 0:
        raise ValueError("no issue with that id")
    log("CLOSE_ISSUE", f"issue {issue_id}")


def mark_attendance(day, records):
    for student_id, status in records.items():
        db.run("""INSERT INTO attendance (student_id, day, status) VALUES (%s, %s, %s)
                  ON DUPLICATE KEY UPDATE status = VALUES(status)""", (student_id, day, status))
    log("MARK_ATTENDANCE", f"{len(records)} students on {day}")


def mark_today(absent_codes):
    """Everyone not listed as absent is marked present for today."""
    ids = {row["admission_no"]: row["id"] for row in db.rows("SELECT id, admission_no FROM students")}
    absent = {code.strip().upper() for code in absent_codes.split(",") if code.strip()}
    mark_attendance(date.today(), {student: "A" if code in absent else "P" for code, student in ids.items()})


def insights():
    """Turn raw numbers into actions - the heart of the viva demo."""
    feed = []
    for row in at_risk()[:3]:
        feed.append(("CRITICAL" if row["pct"] < 65 else "WARN", f"{row['name']} at {row['pct']}%",
                     f"{row['cls']} - below the 75% board-exam cutoff"))
    late = overdue()
    if late:
        feed.append(("WARN", f"{len(late)} overdue library loans",
                     f"worst: {late[0]['title']} ({late[0]['days_late']} days late)"))
    breaches = db.one("SELECT COUNT(*) AS n FROM issues WHERE status = 'OPEN' AND DATEDIFF(CURDATE(), raised_on) > 7")
    if breaches.get("n"):
        feed.append(("CRITICAL", f"{breaches['n']} issues past the 7-day SLA", "escalate to the contractor"))
    for row in db.rows("SELECT title FROM books WHERE copies_available = 0 GROUP BY title HAVING COUNT(*) > 0 LIMIT 2"):
        feed.append(("INFO", f"No copies left: {row['title']}", "reorder from the vendor"))
    return feed or [("INFO", "All clear", "nothing needs attention right now")]


def export_csv(table, path):
    data = db.rows(f"SELECT * FROM {table}")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(data[0].keys()) if data else ["empty"])
        writer.writeheader()
        writer.writerows([{k: str(v) for k, v in row.items()} for row in data])
    return len(data)


def import_students_csv(path):
    added = 0
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if not row.get("name") or not row.get("admission_no"):
                continue
            db.run("""INSERT INTO students (admission_no, name, class_name, section, guardian, phone, source)
                      VALUES (%s, %s, %s, %s, %s, %s, 'import')
                      ON DUPLICATE KEY UPDATE name = VALUES(name), class_name = VALUES(class_name),
                      section = VALUES(section), guardian = VALUES(guardian), phone = VALUES(phone)""",
                   (row["admission_no"], row["name"], row.get("class_name") or "8",
                    (row.get("section") or "A")[0], row.get("guardian", ""), row.get("phone", "")))
            added += 1
    log("IMPORT_CSV", f"{added} rows from {os.path.basename(path)}")
    return added


def backup_all():
    backups = os.path.join(db.DATA, "backups")
    folder = os.path.join(backups, f"{date.today():%Y%m%d}-{len(os.listdir(backups)) + 1:02d}")
    for table in TABLES:
        export_csv(table, os.path.join(folder, f"{table}.csv"))
    log("BACKUP", folder)
    return folder


def ascii_table(headers, records):
    """Pad rows into a monospace table - the whole UI's data grid."""
    body = [[str(cell) for cell in row] for row in records] or [["(no rows)"] + [""] * (len(headers) - 1)]
    widths = [max([len(str(h))] + [len(row[i]) for row in body]) for i, h in enumerate(headers)]
    line = lambda cells: "  ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells)).rstrip()
    return "\n".join([line(headers), "  ".join("-" * w for w in widths)] + [line(r) for r in body])


def bar(pct, width=18):
    filled = int(round(width * max(0.0, min(100.0, float(pct or 0))) / 100))
    return "█" * filled + "·" * (width - filled)
