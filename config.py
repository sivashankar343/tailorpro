import os
from datetime import timedelta


class Config:
    """Application configuration loaded from environment variables."""

    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()

    # Database
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
    _raw_db_url = os.environ.get('DATABASE_URL')
    if _raw_db_url and _raw_db_url.startswith('postgres://'):
        _raw_db_url = _raw_db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _raw_db_url or \
        f"sqlite:///{os.path.join(INSTANCE_DIR, 'tailoring.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'timeout': 30}
    } if not _raw_db_url else {}

    # Session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'

    # WTF CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Excel
    DEFAULT_EXCEL_DIR = r"C:\Users\sivas\OneDrive\Desktop\Excel"
    EXCEL_DIR = os.environ.get('EXCEL_DIR') or (
        DEFAULT_EXCEL_DIR if os.path.exists(DEFAULT_EXCEL_DIR)
        else os.path.join(BASE_DIR, 'excel_data')
    )
    BACKUP_DIR = os.path.join(EXCEL_DIR, 'backups')

    # Rate limiting
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15
