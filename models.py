from datetime import datetime, timezone, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Indian Standard Time (IST, UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_current_ist_time():
    """Return current Indian Standard Time as naive datetime for database storage."""
    return datetime.now(IST).replace(tzinfo=None)

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User account model stored in SQLite."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='staff')
    created_at = db.Column(db.DateTime, default=get_current_ist_time)
    last_login = db.Column(db.DateTime, nullable=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

    def is_locked(self):
        if self.locked_until and self.locked_until > get_current_ist_time():
            return True
        return False

    def __repr__(self):
        return f'<User {self.username}>'


class Company(db.Model):
    """Tailoring company model."""
    __tablename__ = 'companies'
    __table_args__ = (db.UniqueConstraint('created_by', 'company_id', name='uq_user_company_id'),)

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.String(30), nullable=False, index=True)
    company_name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    registration_date = db.Column(db.DateTime, default=get_current_ist_time)
    remarks = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    orders = db.relationship('Order', backref='company', lazy='dynamic')

    def __repr__(self):
        return f'<Company {self.company_id}: {self.company_name}>'


class Order(db.Model):
    """Production order model."""
    __tablename__ = 'orders'
    __table_args__ = (db.UniqueConstraint('created_by', 'order_id', name='uq_user_order_id'),)

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(30), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    garment_type = db.Column(db.String(100), nullable=False)
    machine_line = db.Column(db.String(100), nullable=True)
    order_date = db.Column(db.DateTime, default=get_current_ist_time)
    expected_delivery = db.Column(db.DateTime, nullable=True)
    total_quantity = db.Column(db.Integer, nullable=False, default=0)
    completed_quantity = db.Column(db.Integer, nullable=False, default=0)
    rejected_quantity = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(30), nullable=False, default='Pending')
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=get_current_ist_time)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    production_entries = db.relationship('ProductionEntry', backref='order', lazy='dynamic',
                                         order_by='ProductionEntry.entry_date.desc()')

    @property
    def remaining_quantity(self):
        return max(0, self.total_quantity - self.completed_quantity - self.rejected_quantity)

    def update_status(self):
        if self.remaining_quantity == 0 and self.total_quantity > 0:
            self.status = 'Completed'
        elif self.completed_quantity > 0 or self.rejected_quantity > 0:
            self.status = 'In Progress'
        else:
            self.status = 'Pending'

    def __repr__(self):
        return f'<Order {self.order_id}>'


class ProductionEntry(db.Model):
    """Individual production entry for an order."""
    __tablename__ = 'production_entries'
    __table_args__ = (db.UniqueConstraint('entered_by', 'entry_id', name='uq_user_entry_id'),)

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.String(30), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    quantity_completed = db.Column(db.Integer, nullable=False, default=0)
    quantity_rejected = db.Column(db.Integer, nullable=False, default=0)
    entry_date = db.Column(db.DateTime, default=get_current_ist_time)
    remarks = db.Column(db.Text, nullable=True)
    entered_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    user = db.relationship('User', foreign_keys=[entered_by])

    def __repr__(self):
        return f'<ProductionEntry {self.entry_id}>'


class AuditLog(db.Model):
    """Audit log for security and business events."""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=get_current_ist_time)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    username = db.Column(db.String(80), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    def __repr__(self):
        return f'<AuditLog {self.action} by {self.username}>'


class Invoice(db.Model):
    """GST Tax Invoice model with user tenant isolation."""
    __tablename__ = 'invoices'
    __table_args__ = (db.UniqueConstraint('created_by', 'invoice_number', name='uq_user_invoice_num'),)

    id = db.Column(db.Integer, primary_key=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    invoice_number = db.Column(db.String(50), nullable=False, index=True)
    invoice_date = db.Column(db.Date, nullable=False)
    state = db.Column(db.String(100), default='Tamil Nadu')
    reverse_charge = db.Column(db.String(10), default='NO')

    # Seller details
    seller_name = db.Column(db.String(255), nullable=False)
    seller_address = db.Column(db.Text, nullable=True)
    seller_gstin = db.Column(db.String(50), nullable=True)
    seller_state_code = db.Column(db.String(20), default='33')

    # Buyer / Billed to details
    buyer_name = db.Column(db.String(255), nullable=False)
    buyer_address = db.Column(db.Text, nullable=True)
    buyer_gstin = db.Column(db.String(50), nullable=True)
    buyer_state_code = db.Column(db.String(20), default='33')
    buyer_state = db.Column(db.String(100), default='Tamil Nadu')

    # Consignee / Shipped to details
    ship_name = db.Column(db.String(255), nullable=True)
    ship_address = db.Column(db.Text, nullable=True)
    ship_gstin = db.Column(db.String(50), nullable=True)
    ship_state_code = db.Column(db.String(20), default='33')
    ship_state = db.Column(db.String(100), default='Tamil Nadu')

    # Totals
    total_qty = db.Column(db.Float, default=0.0)
    total_taxable_value = db.Column(db.Float, default=0.0)
    total_cgst = db.Column(db.Float, default=0.0)
    total_sgst = db.Column(db.Float, default=0.0)
    total_igst = db.Column(db.Float, default=0.0)
    total_tax = db.Column(db.Float, default=0.0)
    grand_total = db.Column(db.Float, default=0.0)
    balance_due = db.Column(db.Float, default=0.0)
    amount_in_words = db.Column(db.Text, nullable=True)

    terms_conditions = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=get_current_ist_time)

    items = db.relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan', lazy='joined',
                            order_by='InvoiceItem.item_index.asc()')

    def __repr__(self):
        return f'<Invoice {self.invoice_number} by User {self.created_by}>'


class InvoiceItem(db.Model):
    """Individual line item in an invoice."""
    __tablename__ = 'invoice_items'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False)
    item_index = db.Column(db.Integer, default=1)

    product_name = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Float, default=1.0)
    unit = db.Column(db.String(50), default='')
    rate = db.Column(db.Float, default=0.0)
    taxable_value = db.Column(db.Float, default=0.0)

    cgst_rate = db.Column(db.Float, default=9.0)
    cgst_amount = db.Column(db.Float, default=0.0)
    sgst_rate = db.Column(db.Float, default=9.0)
    sgst_amount = db.Column(db.Float, default=0.0)
    igst_rate = db.Column(db.Float, default=0.0)
    igst_amount = db.Column(db.Float, default=0.0)

    total_amount = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f'<InvoiceItem {self.product_name} of Invoice {self.invoice_id}>'

