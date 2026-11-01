# TailorPro — Tailoring Production Management System

A professional web application for managing tailoring companies, production orders, garment tracking, and business history, inspired by Tally ERP.

## Features

- **User Authentication** — Registration, login, logout with SQLite-backed sessions and password hashing
- **Dashboard** — Real-time production stats, progress bars, and recent activity
- **Company Management** — Add, edit, search, activate/deactivate tailoring companies
- **Order Management** — Create and track garment production orders
- **Production Entry** — Record completed and rejected quantities per order
- **Production History** — Filterable history with company, order, and date range filters
- **Excel Reports** — Full history workbooks and filtered production reports (`.xlsx`)
- **User Management** — Admin-only role management and account unlocking
- **Audit Logging** — All login, logout, and business events are recorded
- **Security** — CSRF protection, password hashing, session protection, rate limiting

## Technology Stack

| Component       | Technology                        |
|-----------------|-----------------------------------|
| Frontend        | HTML, CSS, JavaScript, Bootstrap 5 |
| Backend         | Python Flask                       |
| Database        | SQLite + SQLAlchemy                |
| Excel History   | openpyxl                           |
| Authentication  | Flask-Login + Werkzeug             |
| CSRF Protection | Flask-WTF                          |

## Setup Instructions

### Prerequisites

- Python 3.9 or newer
- pip (Python package manager)

### Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd Tally
   ```

2. **Create a virtual environment:**

   **Windows:**
   ```cmd
   python -m venv venv
   venv\Scripts\activate
   ```

   **Linux / macOS:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**

   Edit the `.env` file and change the `SECRET_KEY`:
   ```
   SECRET_KEY=your-random-secret-key-here
   ```

   To generate a secure key:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

5. **Create the initial administrator account:**
   ```bash
   flask create-admin
   ```
   Follow the prompts to enter the admin's name, username, email, and password.

6. **Start the application:**
   ```bash
   python app.py
   ```
   Open your browser to **http://localhost:5000**

## Project Structure

```
Tally/
├── app.py                  # Main Flask application
├── config.py               # Configuration
├── models.py               # SQLAlchemy database models
├── auth.py                 # Authentication blueprint
├── companies.py            # Company management blueprint
├── orders.py               # Orders & production blueprint
├── excel_service.py        # Excel history service
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (do not commit)
├── README.md               # This file
├── templates/              # Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── companies.html
│   ├── company_form.html
│   ├── company_view.html
│   ├── orders.html
│   ├── order_form.html
│   ├── order_view.html
│   ├── production.html
│   ├── history.html
│   ├── reports.html
│   ├── users.html
│   └── error.html
├── static/
│   ├── css/style.css       # Custom styles
│   └── js/app.js           # Client-side JavaScript
├── instance/
│   └── tailoring.db        # SQLite database (auto-created)
├── excel_data/             # Excel workbooks (auto-created)
│   ├── Company_History.xlsx
│   ├── Order_History.xlsx
│   └── Production_History.xlsx
└── backups/                # Excel backups (auto-created)
```

## Default Roles

| Role  | Access                                                     |
|-------|------------------------------------------------------------|
| Admin | Full access including user management and backups          |
| Staff | Dashboard, companies, orders, production, reports          |

New accounts registered through the web UI are assigned the **staff** role. Only the first admin is created via the CLI command.

## Important Notes

- **Passwords** are hashed with PBKDF2-SHA256 and never stored in plaintext.
- **Login protection** locks accounts after 5 failed attempts for 15 minutes.
- **Excel workbooks** are created automatically on first run.
- **Backups** can be triggered from the Reports page (admin only).
- The SQLite database and Excel files persist across application restarts.
