"""
Seed script to create default admin/staff accounts and initial sample data.
"""

from app import create_app, db
from models import User, Company, Order, ProductionEntry
from excel_service import append_company_history, append_order_history, append_production_history
from datetime import datetime, timezone, timedelta

def seed():
    app = create_app()
    with app.app_context():
        # Check if admin already exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                full_name='System Administrator',
                username='admin',
                email='admin@tailorpro.com',
                role='admin'
            )
            admin.set_password('Admin@123')
            db.session.add(admin)
            print("Created default admin user (username: admin, password: Admin@123)")

        staff = User.query.filter_by(username='staff').first()
        if not staff:
            staff = User(
                full_name='Production Staff',
                username='staff',
                email='staff@tailorpro.com',
                role='staff'
            )
            staff.set_password('Staff@123')
            db.session.add(staff)
            print("Created default staff user (username: staff, password: Staff@123)")

        db.session.commit()

        print("Admin & Staff user accounts ready.")
        print("Database initialized with 0 companies, 0 orders, and 0 production entries.")

if __name__ == '__main__':
    seed()
