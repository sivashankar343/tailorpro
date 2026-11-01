"""
Script to reset all business data (companies, orders, production entries, excel history)
to 0 counts, preserving user accounts so you can log in immediately.
"""
import os
from app import create_app, db
from models import User, Company, Order, ProductionEntry, AuditLog
from excel_service import init_excel_workbooks

def reset_all_to_zero():
    app = create_app()
    with app.app_context():
        # Clear business records
        num_entries = ProductionEntry.query.delete()
        num_orders = Order.query.delete()
        num_companies = Company.query.delete()
        AuditLog.query.delete()
        db.session.commit()
        print(f"Deleted {num_entries} production entries, {num_orders} orders, {num_companies} companies.")

        # Ensure admin and staff accounts exist
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
            print("Admin user ensured (username: admin, password: Admin@123)")

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
            print("Staff user ensured (username: staff, password: Staff@123)")

        db.session.commit()

        # Remove old Excel files and reinitialize clean workbooks with 0 rows
        excel_dir = app.config['EXCEL_DIR']
        for fname in ['Company_History.xlsx', 'Order_History.xlsx', 'Production_History.xlsx']:
            fpath = os.path.join(excel_dir, fname)
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                    print(f"Cleared {fname}")
                except Exception as e:
                    print(f"Could not delete {fname}: {e}")

        init_excel_workbooks()
        print("Reinitialized clean Excel history workbooks with 0 data rows.")

        print("\n=== SYSTEM RESET TO 0 COUNTS COMPLETE ===")
        print(f"Total Companies: {Company.query.count()}")
        print(f"Total Orders: {Order.query.count()}")
        print(f"Total Production Entries: {ProductionEntry.query.count()}")
        print("Ready for live use!")

if __name__ == '__main__':
    reset_all_to_zero()
