# College Placement Management System

A Flask + SQLite web app for managing campus placements — students register,
browse eligible jobs and apply; admins add companies, post jobs, and track
applications through to selection.

## Features

**Student side**
- Register / login
- View jobs filtered automatically by CGPA & branch eligibility
- Apply to jobs (one click, no duplicate applications)
- Track application status: Applied → Shortlisted → Selected / Rejected
- Edit profile (CGPA, phone, resume link)

**Admin side**
- Login with default account: `admin` / `admin123`
- Add / remove companies
- Post jobs with eligibility rules (min CGPA, eligible branches, deadline, package)
- View all registered students
- Review applications and update their status
- Dashboard with overall + branch-wise placement stats

## Setup

1. Install dependencies (Flask is the only requirement):
   ```
   pip install flask
   ```

2. Run the app:
   ```
   cd placement_system
   python app.py
   ```

3. Open your browser at: **http://127.0.0.1:5000/**

The SQLite database (`placement.db`) is created automatically on first run,
along with a default admin account (`admin` / `admin123` — change the
password or edit `init_db()` before deploying anywhere public).

## Project structure

```
placement_system/
├── app.py                  # All routes & logic
├── placement.db             # Created automatically on first run
├── templates/                # Jinja2 HTML templates (Bootstrap 5 styled)
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── student_dashboard.html
│   ├── student_profile.html
│   ├── admin_dashboard.html
│   ├── admin_companies.html
│   ├── admin_jobs.html
│   ├── admin_students.html
│   └── admin_applications.html
└── static/
    └── style.css
```

## Notes for production use

- Change `app.secret_key` in `app.py` to a random secret.
- Change the default admin password.
- Set `debug=False` before deploying.
- Consider adding email verification and password-reset flows for a
  production rollout.
