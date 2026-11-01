import re
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from models import db, User, AuditLog, get_current_ist_time

auth_bp = Blueprint('auth', __name__)


# ---------------------------------------------------------------------------
# WTForms
# ---------------------------------------------------------------------------

class RegistrationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=150)])
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    submit = SubmitField('Create Account')

    def validate_username(self, field):
        if not re.match(r'^[a-zA-Z0-9_]+$', field.data):
            raise ValidationError('Username must contain only letters, numbers, and underscores.')
        if User.query.filter(db.func.lower(User.username) == field.data.lower()).first():
            raise ValidationError('This username is already taken.')

    def validate_email(self, field):
        if User.query.filter(db.func.lower(User.email) == field.data.lower()).first():
            raise ValidationError('This email address is already registered.')


class LoginForm(FlaskForm):
    login_id = StringField('Username or Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_audit(action, details=None, user_id=None, username=None):
    """Write an audit record to the database."""
    entry = AuditLog(
        user_id=user_id or (current_user.id if current_user and current_user.is_authenticated else None),
        username=username or (current_user.username if current_user and current_user.is_authenticated else None),
        action=action,
        details=details,
        ip_address=request.remote_addr
    )
    db.session.add(entry)
    db.session.commit()


def admin_required(f):
    """Decorator that restricts access to admin users."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin():
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            full_name=form.full_name.data.strip(),
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            role='staff'
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        _log_audit('REGISTER', f'New user registered: {user.username}', user_id=user.id, username=user.username)
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        login_id = form.login_id.data.strip()
        user = User.query.filter(
            (db.func.lower(User.username) == login_id.lower()) |
            (db.func.lower(User.email) == login_id.lower())
        ).first()

        if user and user.is_locked():
            remaining = (user.locked_until - get_current_ist_time()).seconds // 60 + 1
            _log_audit('LOGIN_BLOCKED', f'Account locked: {login_id}', username=login_id)
            flash(f'Account is locked. Try again in {remaining} minute(s).', 'danger')
            return render_template('login.html', form=form)

        if user and user.check_password(form.password.data):
            # Successful login
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login = get_current_ist_time()
            db.session.commit()

            login_user(user, remember=False)
            session.permanent = True
            _log_audit('LOGIN_SUCCESS', f'User logged in: {user.username}')

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            # Failed login
            if user:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                from flask import current_app
                max_attempts = current_app.config.get('MAX_LOGIN_ATTEMPTS', 5)
                lockout_min = current_app.config.get('LOGIN_LOCKOUT_MINUTES', 15)
                if user.failed_login_attempts >= max_attempts:
                    user.locked_until = get_current_ist_time() + timedelta(minutes=lockout_min)
                    flash(f'Too many failed attempts. Account locked for {lockout_min} minutes.', 'danger')
                db.session.commit()

            _log_audit('LOGIN_FAILURE', f'Failed login attempt for: {login_id}', username=login_id)
            flash('Invalid username/email or password.', 'danger')

    return render_template('login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    _log_audit('LOGOUT', f'User logged out: {current_user.username}')
    logout_user()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
