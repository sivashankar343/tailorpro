"""
Tailoring Production Management System — main application entry point.
"""

import os
import io
from datetime import datetime, timezone

from flask import Flask, render_template, redirect, url_for, request, flash, send_file
from flask_login import LoginManager, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

from config import Config
from models import db, User, Company, Order, ProductionEntry, AuditLog

load_dotenv()


def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)

    # Ensure instance directory
    os.makedirs(app.config['INSTANCE_DIR'], exist_ok=True)

    # Initialise extensions
    db.init_app(app)
    csrf = CSRFProtect(app)

    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'
    login_manager.session_protection = 'strong'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register blueprints
    from auth import auth_bp
    from companies import companies_bp
    from orders import orders_bp
    from billing import billing_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(billing_bp)

    # Create tables & initialise Excel workbooks
    with app.app_context():
        db.create_all()
        from excel_service import init_excel_workbooks
        init_excel_workbooks()
        if not User.query.filter_by(username='admin').first():
            admin = User(
                full_name='System Administrator',
                username='admin',
                email='admin@tailorpro.com',
                role='admin'
            )
            admin.set_password('Admin@123')
            db.session.add(admin)
            db.session.commit()

    # -----------------------------------------------------------------------
    # Main routes
    # -----------------------------------------------------------------------

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('auth.login'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        total_companies = Company.query.filter_by(created_by=current_user.id, is_active=True).count()
        total_orders = Order.query.filter_by(created_by=current_user.id).count()
        active_orders = Order.query.filter(Order.created_by == current_user.id, Order.status != 'Completed').count()
        total_received = db.session.query(db.func.coalesce(db.func.sum(Order.total_quantity), 0)).filter(Order.created_by == current_user.id).scalar()
        total_completed = db.session.query(db.func.coalesce(db.func.sum(Order.completed_quantity), 0)).filter(Order.created_by == current_user.id).scalar()
        total_rejected = db.session.query(db.func.coalesce(db.func.sum(Order.rejected_quantity), 0)).filter(Order.created_by == current_user.id).scalar()
        total_remaining = total_received - total_completed - total_rejected

        recent_entries = (ProductionEntry.query
                          .join(Order).join(Company)
                          .filter(Order.created_by == current_user.id)
                          .order_by(ProductionEntry.entry_date.desc())
                          .limit(10).all())

        return render_template('dashboard.html',
                               total_companies=total_companies,
                               total_orders=total_orders,
                               active_orders=active_orders,
                               total_received=total_received,
                               total_completed=total_completed,
                               total_rejected=total_rejected,
                               total_remaining=max(0, total_remaining),
                               recent_entries=recent_entries)

    # -----------------------------------------------------------------------
    # Reports & Excel download
    # -----------------------------------------------------------------------

    @app.route('/reports')
    @login_required
    def reports():
        companies = Company.query.filter_by(created_by=current_user.id).order_by(Company.company_name).all()
        orders_list = Order.query.filter_by(created_by=current_user.id).order_by(Order.order_id.desc()).all()
        return render_template('reports.html', companies=companies, orders_list=orders_list)

    @app.route('/reports/download/<filetype>')
    @login_required
    def download_excel(filetype):
        from excel_service import export_user_history
        wb = export_user_history(current_user.id, filetype)
        if not wb:
            flash('Invalid file type.', 'danger')
            return redirect(url_for('reports'))

        file_map = {
            'company': f'Company_History_{current_user.username}.xlsx',
            'order': f'Order_History_{current_user.username}.xlsx',
            'production': f'Production_History_{current_user.username}.xlsx',
        }
        filename = file_map.get(filetype, 'Export.xlsx')

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        # Also save a copy to the Desktop Excel directory
        try:
            local_path = os.path.join(app.config['EXCEL_DIR'], filename)
            wb.save(local_path)
        except Exception:
            pass

        audit = AuditLog(user_id=current_user.id, username=current_user.username,
                         action='REPORT_EXPORTED',
                         details=f'Downloaded: {filename}',
                         ip_address=request.remote_addr)
        db.session.add(audit)
        db.session.commit()

        return send_file(buf, as_attachment=True, download_name=filename,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    @app.route('/reports/filtered')
    @login_required
    def download_filtered_report():
        company_id = request.args.get('company', '')
        order_id = request.args.get('order', '')
        date_from_str = request.args.get('date_from', '')
        date_to_str = request.args.get('date_to', '')

        date_from = None
        date_to = None
        if date_from_str:
            try:
                date_from = datetime.strptime(date_from_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, '%Y-%m-%d').replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc)
            except ValueError:
                pass

        from excel_service import generate_filtered_report
        wb = generate_filtered_report(
            user_id=current_user.id,
            company_id=company_id or None,
            order_id=order_id or None,
            date_from=date_from,
            date_to=date_to
        )

        report_name = f'Production_Report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        local_report_path = os.path.join(app.config['EXCEL_DIR'], report_name)
        try:
            wb.save(local_report_path)
        except Exception:
            pass

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        audit = AuditLog(user_id=current_user.id, username=current_user.username,
                         action='REPORT_EXPORTED',
                         details=f'Filtered report exported and saved to {local_report_path}',
                         ip_address=request.remote_addr)
        db.session.add(audit)
        db.session.commit()

        return send_file(buf, as_attachment=True,
                         download_name=report_name,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    @app.route('/reports/backup', methods=['POST'])
    @login_required
    def create_backup_route():
        from auth import admin_required as _chk
        if not current_user.is_admin():
            flash('Only administrators can create backups.', 'danger')
            return redirect(url_for('reports'))

        from excel_service import create_backup
        create_backup()
        flash('Backup created successfully.', 'success')
        return redirect(url_for('reports'))

    # -----------------------------------------------------------------------
    # User management (admin only)
    # -----------------------------------------------------------------------

    @app.route('/users')
    @login_required
    def manage_users():
        if not current_user.is_admin():
            flash('Access denied.', 'danger')
            return redirect(url_for('dashboard'))
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template('users.html', users=users)

    @app.route('/users/toggle-role/<int:user_id>', methods=['POST'])
    @login_required
    def toggle_role(user_id):
        if not current_user.is_admin():
            flash('Access denied.', 'danger')
            return redirect(url_for('dashboard'))

        user = User.query.get_or_404(user_id)
        if user.id == current_user.id:
            flash('You cannot change your own role.', 'warning')
            return redirect(url_for('manage_users'))

        user.role = 'staff' if user.role == 'admin' else 'admin'
        db.session.commit()

        audit = AuditLog(user_id=current_user.id, username=current_user.username,
                         action='ROLE_CHANGED',
                         details=f'Changed {user.username} role to {user.role}',
                         ip_address=request.remote_addr)
        db.session.add(audit)
        db.session.commit()

        flash(f'User {user.username} role changed to {user.role}.', 'success')
        return redirect(url_for('manage_users'))

    @app.route('/users/unlock/<int:user_id>', methods=['POST'])
    @login_required
    def unlock_user(user_id):
        if not current_user.is_admin():
            flash('Access denied.', 'danger')
            return redirect(url_for('dashboard'))

        user = User.query.get_or_404(user_id)
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()

        flash(f'User {user.username} has been unlocked.', 'success')
        return redirect(url_for('manage_users'))

    # -----------------------------------------------------------------------
    # Error handlers
    # -----------------------------------------------------------------------

    @app.errorhandler(404)
    def not_found(e):
        return render_template('error.html', code=404, message='Page not found.'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('error.html', code=403, message='Access forbidden.'), 403

    @app.errorhandler(500)
    def server_error(e):
        return render_template('error.html', code=500, message='Internal server error.'), 500

    return app


# ---------------------------------------------------------------------------
# CLI command: create admin
# ---------------------------------------------------------------------------

app = create_app()


@app.cli.command('create-admin')
def create_admin_cmd():
    """Create the initial administrator account via CLI."""
    import getpass

    print('\n=== Create Administrator Account ===')
    full_name = input('Full name: ').strip()
    username = input('Username: ').strip()
    email = input('Email: ').strip()
    password = getpass.getpass('Password: ')
    password2 = getpass.getpass('Confirm password: ')

    if password != password2:
        print('Error: Passwords do not match.')
        return

    if len(password) < 8:
        print('Error: Password must be at least 8 characters.')
        return

    if User.query.filter((User.username == username) | (User.email == email)).first():
        print('Error: Username or email already exists.')
        return

    admin = User(
        full_name=full_name,
        username=username,
        email=email,
        role='admin'
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f'Administrator "{username}" created successfully!')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
