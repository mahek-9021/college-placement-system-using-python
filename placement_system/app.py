import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g
)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "placement.db")

app = Flask(__name__)
app.secret_key = "college-placement-secret-key-change-in-production"

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    cur = db.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            roll_no TEXT UNIQUE NOT NULL,
            branch TEXT NOT NULL,
            cgpa REAL NOT NULL,
            phone TEXT,
            resume_link TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            website TEXT
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            min_cgpa REAL DEFAULT 0,
            eligible_branches TEXT,
            package TEXT,
            location TEXT,
            deadline TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Applied',
            applied_at TEXT NOT NULL,
            UNIQUE(student_id, job_id),
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
        );
        """
    )

    # Default admin account: username = admin, password = admin123
    cur.execute("SELECT COUNT(*) FROM admins")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO admins (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123")),
        )

    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if "user_type" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            if role and session.get("user_type") != role:
                flash("You are not authorized to view that page.", "danger")
                return redirect(url_for("index"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    db = get_db()
    stats = {
        "students": db.execute("SELECT COUNT(*) c FROM students").fetchone()["c"],
        "companies": db.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"],
        "jobs": db.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"],
        "placed": db.execute(
            "SELECT COUNT(DISTINCT student_id) c FROM applications WHERE status='Selected'"
        ).fetchone()["c"],
    }
    recent_jobs = db.execute(
        """SELECT jobs.*, companies.name AS company_name
           FROM jobs JOIN companies ON jobs.company_id = companies.id
           ORDER BY jobs.created_at DESC LIMIT 5"""
    ).fetchall()
    return render_template("index.html", stats=stats, recent_jobs=recent_jobs)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role")
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        db = get_db()

        if role == "admin":
            user = db.execute(
                "SELECT * FROM admins WHERE username = ?", (identifier,)
            ).fetchone()
            if user and check_password_hash(user["password"], password):
                session.clear()
                session["user_type"] = "admin"
                session["user_id"] = user["id"]
                session["user_name"] = user["username"]
                flash("Welcome back, Admin!", "success")
                return redirect(url_for("admin_dashboard"))
        else:
            user = db.execute(
                "SELECT * FROM students WHERE email = ?", (identifier,)
            ).fetchone()
            if user and check_password_hash(user["password"], password):
                session.clear()
                session["user_type"] = "student"
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                flash(f"Welcome back, {user['name']}!", "success")
                return redirect(url_for("student_dashboard"))

        flash("Invalid credentials. Please try again.", "danger")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        roll_no = request.form.get("roll_no", "").strip()
        branch = request.form.get("branch", "").strip()
        cgpa = request.form.get("cgpa", "0")
        phone = request.form.get("phone", "").strip()
        resume_link = request.form.get("resume_link", "").strip()

        if not (name and email and password and roll_no and branch):
            flash("Please fill in all required fields.", "danger")
            return render_template("register.html")

        try:
            cgpa_val = float(cgpa)
        except ValueError:
            cgpa_val = 0.0

        db = get_db()
        try:
            db.execute(
                """INSERT INTO students
                   (name, email, password, roll_no, branch, cgpa, phone, resume_link, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name, email, generate_password_hash(password), roll_no,
                    branch, cgpa_val, phone, resume_link,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            db.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email or Roll No already registered.", "danger")

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Student routes
# ---------------------------------------------------------------------------

@app.route("/student/dashboard")
@login_required(role="student")
def student_dashboard():
    db = get_db()
    student = db.execute(
        "SELECT * FROM students WHERE id = ?", (session["user_id"],)
    ).fetchone()

    jobs = db.execute(
        """SELECT jobs.*, companies.name AS company_name
           FROM jobs JOIN companies ON jobs.company_id = companies.id
           WHERE jobs.min_cgpa <= ?
           ORDER BY jobs.created_at DESC""",
        (student["cgpa"],),
    ).fetchall()

    eligible_jobs = [
        j for j in jobs
        if not j["eligible_branches"]
        or student["branch"].lower() in [b.strip().lower() for b in j["eligible_branches"].split(",")]
    ]

    applications = db.execute(
        """SELECT applications.*, jobs.title, companies.name AS company_name
           FROM applications
           JOIN jobs ON applications.job_id = jobs.id
           JOIN companies ON jobs.company_id = companies.id
           WHERE applications.student_id = ?
           ORDER BY applications.applied_at DESC""",
        (student["id"],),
    ).fetchall()

    applied_job_ids = {a["job_id"] for a in applications}

    return render_template(
        "student_dashboard.html",
        student=student,
        jobs=eligible_jobs,
        applications=applications,
        applied_job_ids=applied_job_ids,
    )


@app.route("/student/apply/<int:job_id>", methods=["POST"])
@login_required(role="student")
def apply_job(job_id):
    db = get_db()
    student = db.execute(
        "SELECT * FROM students WHERE id = ?", (session["user_id"],)
    ).fetchone()
    job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    if not job:
        flash("Job not found.", "danger")
        return redirect(url_for("student_dashboard"))

    if student["cgpa"] < job["min_cgpa"]:
        flash("You do not meet the minimum CGPA requirement for this job.", "danger")
        return redirect(url_for("student_dashboard"))

    if job["eligible_branches"]:
        allowed = [b.strip().lower() for b in job["eligible_branches"].split(",")]
        if student["branch"].lower() not in allowed:
            flash("Your branch is not eligible for this job.", "danger")
            return redirect(url_for("student_dashboard"))

    try:
        db.execute(
            "INSERT INTO applications (student_id, job_id, status, applied_at) VALUES (?, ?, 'Applied', ?)",
            (student["id"], job_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        db.commit()
        flash("Application submitted successfully!", "success")
    except sqlite3.IntegrityError:
        flash("You have already applied for this job.", "warning")

    return redirect(url_for("student_dashboard"))


@app.route("/student/profile", methods=["GET", "POST"])
@login_required(role="student")
def student_profile():
    db = get_db()
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        resume_link = request.form.get("resume_link", "").strip()
        cgpa = request.form.get("cgpa", "0")
        try:
            cgpa_val = float(cgpa)
        except ValueError:
            cgpa_val = 0.0

        db.execute(
            "UPDATE students SET phone = ?, resume_link = ?, cgpa = ? WHERE id = ?",
            (phone, resume_link, cgpa_val, session["user_id"]),
        )
        db.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("student_profile"))

    student = db.execute(
        "SELECT * FROM students WHERE id = ?", (session["user_id"],)
    ).fetchone()
    return render_template("student_profile.html", student=student)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route("/admin/dashboard")
@login_required(role="admin")
def admin_dashboard():
    db = get_db()
    stats = {
        "students": db.execute("SELECT COUNT(*) c FROM students").fetchone()["c"],
        "companies": db.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"],
        "jobs": db.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"],
        "applications": db.execute("SELECT COUNT(*) c FROM applications").fetchone()["c"],
        "placed": db.execute(
            "SELECT COUNT(DISTINCT student_id) c FROM applications WHERE status='Selected'"
        ).fetchone()["c"],
    }
    branch_stats = db.execute(
        """SELECT branch, COUNT(*) as total,
           SUM(CASE WHEN id IN (
               SELECT student_id FROM applications WHERE status='Selected'
           ) THEN 1 ELSE 0 END) as placed
           FROM students GROUP BY branch"""
    ).fetchall()
    return render_template("admin_dashboard.html", stats=stats, branch_stats=branch_stats)


@app.route("/admin/companies", methods=["GET", "POST"])
@login_required(role="admin")
def admin_companies():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        website = request.form.get("website", "").strip()
        if name:
            db.execute(
                "INSERT INTO companies (name, description, website) VALUES (?, ?, ?)",
                (name, description, website),
            )
            db.commit()
            flash("Company added successfully.", "success")
        return redirect(url_for("admin_companies"))

    companies = db.execute("SELECT * FROM companies ORDER BY id DESC").fetchall()
    return render_template("admin_companies.html", companies=companies)


@app.route("/admin/companies/delete/<int:company_id>", methods=["POST"])
@login_required(role="admin")
def delete_company(company_id):
    db = get_db()
    db.execute("DELETE FROM companies WHERE id = ?", (company_id,))
    db.commit()
    flash("Company removed.", "info")
    return redirect(url_for("admin_companies"))


@app.route("/admin/jobs", methods=["GET", "POST"])
@login_required(role="admin")
def admin_jobs():
    db = get_db()
    if request.method == "POST":
        company_id = request.form.get("company_id")
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        min_cgpa = request.form.get("min_cgpa", "0")
        eligible_branches = request.form.get("eligible_branches", "").strip()
        package = request.form.get("package", "").strip()
        location = request.form.get("location", "").strip()
        deadline = request.form.get("deadline", "").strip()

        try:
            min_cgpa_val = float(min_cgpa)
        except ValueError:
            min_cgpa_val = 0.0

        if company_id and title:
            db.execute(
                """INSERT INTO jobs
                   (company_id, title, description, min_cgpa, eligible_branches,
                    package, location, deadline, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    company_id, title, description, min_cgpa_val, eligible_branches,
                    package, location, deadline,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            db.commit()
            flash("Job posted successfully.", "success")
        return redirect(url_for("admin_jobs"))

    jobs = db.execute(
        """SELECT jobs.*, companies.name AS company_name
           FROM jobs JOIN companies ON jobs.company_id = companies.id
           ORDER BY jobs.id DESC"""
    ).fetchall()
    companies = db.execute("SELECT * FROM companies ORDER BY name").fetchall()
    return render_template("admin_jobs.html", jobs=jobs, companies=companies)


@app.route("/admin/jobs/delete/<int:job_id>", methods=["POST"])
@login_required(role="admin")
def delete_job(job_id):
    db = get_db()
    db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    db.commit()
    flash("Job removed.", "info")
    return redirect(url_for("admin_jobs"))


@app.route("/admin/students")
@login_required(role="admin")
def admin_students():
    db = get_db()
    students = db.execute("SELECT * FROM students ORDER BY name").fetchall()
    return render_template("admin_students.html", students=students)


@app.route("/admin/applications", methods=["GET", "POST"])
@login_required(role="admin")
def admin_applications():
    db = get_db()
    if request.method == "POST":
        app_id = request.form.get("application_id")
        new_status = request.form.get("status")
        if app_id and new_status in ("Applied", "Shortlisted", "Selected", "Rejected"):
            db.execute(
                "UPDATE applications SET status = ? WHERE id = ?", (new_status, app_id)
            )
            db.commit()
            flash("Application status updated.", "success")
        return redirect(url_for("admin_applications"))

    applications = db.execute(
        """SELECT applications.*, students.name AS student_name, students.roll_no,
                  students.branch, students.cgpa, jobs.title, companies.name AS company_name
           FROM applications
           JOIN students ON applications.student_id = students.id
           JOIN jobs ON applications.job_id = jobs.id
           JOIN companies ON jobs.company_id = companies.id
           ORDER BY applications.applied_at DESC"""
    ).fetchall()
    return render_template("admin_applications.html", applications=applications)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        init_db()
    else:
        init_db()  # safe: CREATE TABLE IF NOT EXISTS
    app.run(debug=True, host="0.0.0.0", port=5000)
