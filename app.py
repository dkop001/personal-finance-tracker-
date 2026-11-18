"""CAMPUS//OS - customtkinter console over MySQL. Usage: py -3.13 app.py [--reset|--demo|--fresh]"""

import os
import sys
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox

import customtkinter as ctk

import db
import logic

INK, PANEL, PANEL2, LINE = "#060A0F", "#0B1219", "#101A23", "#1C2A37"
TEXT, MUTED, DIM = "#E7EFF7", "#71838F", "#3F5260"
CYAN, GREEN, AMBER, RED, HOVER = "#25D0E8", "#3FDD9A", "#F5B84B", "#FF6B6B", "#1B2B38"
FONT, SEV = "Consolas", {"CRITICAL": RED, "WARN": AMBER, "INFO": CYAN}
NAV = [("DASHBOARD", "dashboard"), ("STUDENTS", "students"), ("ATTENDANCE", "attendance"),
       ("LIBRARY", "library"), ("ISSUES", "issues"), ("SYSTEM", "system")]

def label(parent, text, color=TEXT, size=11, weight="normal", **kw):
    return ctk.CTkLabel(parent, text=str(text), text_color=color, font=(FONT, size, weight), **kw)

def button(parent, text, command, **kw):
    return ctk.CTkButton(parent, text=text, command=command, height=34, corner_radius=6, fg_color=PANEL2,
                         hover_color=HOVER, border_color=LINE, border_width=1, text_color=TEXT,
                         font=(FONT, 10, "bold"), **kw)

def panel(parent, title=""):
    frame = ctk.CTkFrame(parent, fg_color=PANEL, border_color=LINE, border_width=1, corner_radius=8)
    if title:
        label(frame, title, CYAN, 9, "bold").pack(anchor="w", padx=14, pady=(11, 2))
    return frame

class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=INK)
        width, height = min(1340, int(self.winfo_screenwidth() * 0.94)), min(840, int(self.winfo_screenheight() * 0.92))
        self.title("CAMPUS//OS - SCHOOL OPERATIONS"); self.geometry(f"{width}x{height}+0+0"); self.minsize(900, 560)
        self.query, self.screen, self.nav = "", "dashboard", {}; self.build_sidebar()
        self.content = ctk.CTkScrollableFrame(self, fg_color=INK, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)
        self.go("dashboard")
    def build_sidebar(self):
        side = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=PANEL)
        side.pack(side="left", fill="y"); side.pack_propagate(False)
        label(side, "CAMPUS//OS", TEXT, 16, "bold").pack(anchor="w", padx=18, pady=(22, 0))
        label(side, "SCHOOL OPERATIONS CORE", MUTED, 8).pack(anchor="w", padx=18, pady=(0, 16))
        for text, key in NAV:
            self.nav[key] = ctk.CTkButton(side, text=text, anchor="w", height=36, corner_radius=6, hover_color=PANEL2,
                                          fg_color="transparent", text_color=MUTED, font=(FONT, 10, "bold"),
                                          command=lambda k=key: self.go(k))
            self.nav[key].pack(fill="x", padx=12, pady=2)
        self.status = label(side, f"mysql://{db.HOST}/{db.DATABASE}", MUTED, 9, wraplength=186, justify="left")
        self.status.pack(side="bottom", anchor="w", padx=18, pady=14)
    def go(self, name):
        self.screen = name
        for key, widget in self.nav.items():
            widget.configure(fg_color=PANEL2 if key == name else "transparent",
                             text_color=TEXT if key == name else MUTED)
        for widget in self.content.winfo_children():
            widget.destroy()
        getattr(self, "screen_" + name)()
    def header(self, title, subtitle):
        box = ctk.CTkFrame(self.content, fg_color="transparent"); box.pack(fill="x", padx=20, pady=(18, 8))
        label(box, title, TEXT, 19, "bold").pack(anchor="w")
        label(box, subtitle, MUTED, 10).pack(anchor="w")
    def kpis(self, cards):
        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", padx=15, pady=(0, 10))
        for index, (heading, value, note, color) in enumerate(cards):
            card = ctk.CTkFrame(row, width=1, fg_color=PANEL, border_color=color, border_width=1, corner_radius=8)
            card.grid(row=0, column=index, sticky="nsew", padx=5); row.columnconfigure(index, weight=1)
            label(card, heading, MUTED, 9, "bold").pack(anchor="w", padx=14, pady=(12, 0))
            label(card, value, TEXT, 24, "bold").pack(anchor="w", padx=14)
            label(card, note, MUTED, 9).pack(anchor="w", padx=14, pady=(0, 10))
    def table(self, title, headers, records, height=14, colors=None):
        box = panel(self.content, title); box.pack(fill="x", padx=20, pady=6)
        view = tk.Text(box, bg=PANEL, fg=TEXT, font=("Consolas", 11), bd=0, highlightthickness=0, width=1,
                       height=max(2, min(len(records) + 3, height)), padx=14, pady=8, wrap="none")
        view.insert("1.0", logic.ascii_table(headers, records))
        view.tag_configure("head", foreground=CYAN); view.tag_add("head", "1.0", "1.end")
        for index, color in enumerate(colors or []):
            view.tag_configure(f"r{index}", foreground=color)
            view.tag_add(f"r{index}", f"{index + 3}.0", f"{index + 3}.end")
        view.configure(state="disabled"); view.pack(fill="x")
    def action_row(self, specs):
        row = ctk.CTkFrame(self.content, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 8))
        for text, command in specs:
            button(row, text, command).pack(side="left", padx=(0, 8))
    def ask(self, title, fields, save):
        win = ctk.CTkToplevel(self); win.title(title); win.geometry(f"430x{120 + 40 * len(fields)}")
        win.configure(fg_color=INK); win.transient(self); win.grab_set()
        label(win, title, CYAN, 12, "bold").pack(anchor="w", padx=20, pady=(16, 8))
        entries = {}
        for name, key in fields:
            entries[key] = ctk.CTkEntry(win, placeholder_text=name, height=32, fg_color=PANEL2,
                                        border_color=LINE, text_color=TEXT, font=(FONT, 11))
            entries[key].pack(fill="x", padx=20, pady=4)
        def commit():
            try:
                message = save({key: entry.get().strip() for key, entry in entries.items()})
            except Exception as exc:
                return self.finish(f"{title}: {exc}", RED, stay=True)
            win.destroy(); self.finish(message or f"{title.lower()} saved")
        button(win, "SAVE", commit).pack(fill="x", padx=20, pady=16)
    def finish(self, message, color=GREEN, stay=False):
        self.status.configure(text=str(message)[:150], text_color=color)
        if not stay:
            self.go(self.screen)
    # ------------------------------------------------------------------ screens
    def screen_dashboard(self):
        live, classes = logic.stats(), logic.attendance_by_class()
        colors = [GREEN if float(c["pct"]) >= 90 else AMBER if float(c["pct"]) >= 75 else RED for c in classes]
        self.header("MISSION CONTROL", f"Every number below is a live MySQL query. Attendance window {live['span']}.")
        self.kpis([("STUDENTS", live["students"], "on roll", CYAN),
                   ("ATTENDANCE", f"{live['attendance']}%", "all recorded days", GREEN),
                   ("OPEN ISSUES", live["open_issues"], "awaiting action", AMBER),
                   ("BOOKS OUT", live["issued"], "active loans", RED)])
        self.table("ATTENDANCE BY CLASS // GROUP BY + AVG", ["CLASS", "BAR", "ATT %"],
                   [(c["label"], logic.bar(c["pct"]), f"{c['pct']}%") for c in classes], 8, colors)
        self.table("SIGNAL FEED // INSIGHT ENGINE", ["SEVERITY", "SIGNAL", "ACTION"], logic.insights(), 8)
    def screen_students(self):
        records = [(r["admission_no"], r["name"], r["cls"], r["guardian"], f"{r['pct']}%") for r in logic.students(self.query)]
        self.header("STUDENT REGISTRY", "File handling lives here: import a CSV, export the register.")
        self.action_row([
            ("SEARCH", lambda: self.ask("SEARCH REGISTRY", [("name or admission number", "term")], self.search)),
            ("ADD STUDENT", lambda: self.ask("NEW STUDENT", [
                ("admission number", "admission_no"), ("full name", "name"), ("class", "class_name"),
                ("section", "section"), ("guardian", "guardian"), ("phone", "phone")], logic.add_student)),
            ("IMPORT CSV", self.import_csv),
            ("EXPORT CSV", lambda: self.finish(f"{logic.export_csv('students', os.path.join(db.DATA, 'exports', 'students.csv'))} rows"))])
        self.table(f"REGISTER // {len(records)} RECORDS", ["ADM NO", "NAME", "CLASS", "GUARDIAN", "ATT %"], records, 26)
    def screen_attendance(self):
        self.header("ATTENDANCE ANALYTICS", "A GROUP BY average and a HAVING cutoff decide who is at risk.")
        self.action_row([("MARK TODAY", lambda: self.ask(
            "MARK TODAY", [("absent admission numbers, comma separated", "absent")],
            lambda fields: logic.mark_today(fields["absent"])))])
        self.table("CLASS AVERAGES // GROUP BY", ["CLASS", "STUDENTS", "ATT %"],
                   [(r["label"], r["students"], f"{r['pct']}%") for r in logic.attendance_by_class()])
        self.table("AT RISK // HAVING AVG(status='P') < 75", ["ADM NO", "NAME", "CLASS", "DAYS", "ATT %"],
                   [(r["admission_no"], r["name"], r["cls"], r["days"], f"{r['pct']}%") for r in logic.at_risk()])
    def screen_library(self):
        self.header("LIBRARY INTELLIGENCE", "Catalogue, live loans and overdue notices from DATEDIFF.")
        self.action_row([
            ("ISSUE BOOK", lambda: self.ask("ISSUE BOOK", [("book id", "book"), ("student id", "student")],
                                            lambda f: logic.issue_book(int(f["book"]), int(f["student"])))),
            ("RETURN BOOK", lambda: self.ask("RETURN BOOK", [("loan id from LIVE LOANS", "loan")],
                                             lambda f: logic.return_loan(int(f["loan"]))))])
        self.table("CATALOGUE // COPIES REMAINING", ["ID", "TITLE", "CATEGORY", "AVAIL", "TOTAL"], [
            (r["id"], r["title"], r["category"], r["copies_available"], r["copies_total"]) for r in logic.books()], 14)
        self.table("LIVE LOANS // ORDER BY DUE DATE", ["ID", "STUDENT", "TITLE", "DUE"],
                   [(r["id"], r["name"], r["title"], r["due_on"]) for r in logic.open_loans()], 10)
        self.table("OVERDUE // DATEDIFF(CURDATE(), due_on)", ["ID", "STUDENT", "TITLE", "DAYS LATE"],
                   [(r["id"], r["name"], r["title"], r["days_late"]) for r in logic.overdue()], 8)
    def screen_issues(self):
        records = [(r["id"], r["title"], r["category"], r["location"], r["priority"], r["status"], r["age"]) for r in logic.issues()]
        self.header("ISSUE TRACKER", "Priority-ordered queue; closing an issue is a plain SQL UPDATE.")
        self.action_row([
            ("NEW ISSUE", lambda: self.ask("NEW ISSUE", [("title", "title"), ("category", "category"),
                                                         ("location", "location"), ("priority CRITICAL..LOW", "priority")],
                                           logic.raise_issue)),
            ("CLOSE ISSUE", lambda: self.ask("CLOSE ISSUE", [("issue id", "issue")],
                                             lambda f: logic.close_issue(int(f["issue"]))))])
        self.table(f"QUEUE // {len(records)} ISSUES",
                   ["ID", "TITLE", "CATEGORY", "LOCATION", "PRIORITY", "STATUS", "AGE"], records, 18)
    def screen_system(self):
        counts = [(table, db.one(f"SELECT COUNT(*) AS n FROM {table}")["n"]) for table in logic.TABLES]
        self.header("SYSTEM CONSOLE", "Schema health, CSV backups, demo reset and demo purge.")
        self.action_row([("BACKUP ALL TABLES", lambda: self.finish(f"backup written to {logic.backup_all()}")),
                         ("RESET + LOAD DEMO", lambda: self.finish(f"demo campus: {db.seed_demo(reset=True)['students']} students loaded")),
                         ("PURGE DEMO ROWS", lambda: self.finish(f"{db.purge_demo()} demo students removed, real rows kept"))])
        self.table("LIVE ROW COUNTS // COUNT(*)", ["TABLE", "ROWS"], counts, 8)
    # ------------------------------------------------------------------ actions
    def search(self, fields):
        self.query = fields["term"]; self.go("students")
        return f"{len(logic.students(self.query))} matches for '{self.query or 'all'}'"
    def import_csv(self):
        path = filedialog.askopenfilename(title="Select students.csv", filetypes=[("CSV files", "*.csv")],
                                          initialdir=os.path.join(db.DATA, "imports"))
        if not path:
            return
        try:
            self.finish(f"imported {logic.import_students_csv(path)} students")
        except Exception as exc:
            self.finish(f"import failed: {exc}", RED)

def main():
    ctk.set_appearance_mode("dark"); App().mainloop()

if __name__ == "__main__":
    if "--fresh" in sys.argv:
        db.create_schema(reset=True); print("campus_os ready: empty schema, add real students in the app")
    elif "--demo" in sys.argv or "--reset" in sys.argv:
        print("campus_os ready:", db.seed_demo(reset="--reset" in sys.argv))
    try:
        main()
    except SystemExit as exc:
        messagebox.showerror("CAMPUS//OS", str(exc))
