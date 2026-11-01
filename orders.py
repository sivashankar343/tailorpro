from datetime import datetime, timezone

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, TextAreaField, SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Length

from models import db, Order, Company, ProductionEntry, AuditLog

orders_bp = Blueprint('orders', __name__, url_prefix='/orders')


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

class OrderForm(FlaskForm):
    company_id = SelectField('Company', validators=[DataRequired()], coerce=int)
    garment_type = StringField('Garment Type', validators=[DataRequired(), Length(max=100)])
    machine_line = StringField('Machine / Production Line', validators=[Optional(), Length(max=100)])
    expected_delivery = DateField('Expected Delivery Date', validators=[Optional()], format='%Y-%m-%d')
    total_quantity = IntegerField('Total Quantity Received', validators=[DataRequired(), NumberRange(min=1)])
    remarks = TextAreaField('Remarks', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Save Order')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if current_user and current_user.is_authenticated:
            self.company_id.choices = [
                (c.id, f'{c.company_id} - {c.company_name}')
                for c in Company.query.filter_by(created_by=current_user.id, is_active=True).order_by(Company.company_name).all()
            ]
        else:
            self.company_id.choices = []


class ProductionForm(FlaskForm):
    order_id = SelectField('Order', validators=[DataRequired()], coerce=int)
    quantity_completed = IntegerField('Return Completed', validators=[DataRequired(), NumberRange(min=1)], default=0)
    quantity_rejected = IntegerField('Quantity Rejected', validators=[Optional(), NumberRange(min=0)], default=0)
    remarks = TextAreaField('Remarks', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Record Return Entry')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if current_user and current_user.is_authenticated:
            active_orders = Order.query.filter(
                Order.created_by == current_user.id,
                Order.status != 'Completed'
            ).order_by(Order.order_date.desc()).all()
            self.order_id.choices = [
                (o.id, f'{o.order_id} — {o.company.company_name} — {o.garment_type} (Remaining: {o.remaining_quantity})')
                for o in active_orders
            ]
        else:
            self.order_id.choices = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_order_id(user_id):
    count = Order.query.filter_by(created_by=user_id).count()
    return f'ORD-{count + 1:05d}'


def _generate_entry_id(user_id):
    count = ProductionEntry.query.filter_by(entered_by=user_id).count()
    return f'PRD-{count + 1:06d}'


# ---------------------------------------------------------------------------
# Order routes
# ---------------------------------------------------------------------------

@orders_bp.route('/')
@login_required
def list_orders():
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    page = request.args.get('page', 1, type=int)

    query = Order.query.filter_by(created_by=current_user.id).join(Company)

    if search:
        pattern = f'%{search}%'
        query = query.filter(
            Order.order_id.ilike(pattern) |
            Company.company_name.ilike(pattern) |
            Order.garment_type.ilike(pattern)
        )

    if status_filter:
        query = query.filter(Order.status == status_filter)

    orders = query.order_by(Order.order_date.desc()).paginate(page=page, per_page=15, error_out=False)
    return render_template('orders.html', orders=orders, search=search, status_filter=status_filter)


@orders_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_order():
    form = OrderForm()
    if form.validate_on_submit():
        # Ensure company belongs to current user
        Company.query.filter_by(id=form.company_id.data, created_by=current_user.id).first_or_404()

        order = Order(
            order_id=_generate_order_id(current_user.id),
            company_id=form.company_id.data,
            garment_type=form.garment_type.data.strip(),
            machine_line=form.machine_line.data.strip() if form.machine_line.data else None,
            expected_delivery=datetime.combine(form.expected_delivery.data, datetime.min.time()).replace(
                tzinfo=timezone.utc) if form.expected_delivery.data else None,
            total_quantity=form.total_quantity.data,
            remarks=form.remarks.data.strip() if form.remarks.data else None,
            created_by=current_user.id
        )
        db.session.add(order)
        db.session.commit()

        audit = AuditLog(user_id=current_user.id, username=current_user.username,
                         action='ORDER_CREATED',
                         details=f'Order created: {order.order_id}, Qty: {order.total_quantity}',
                         ip_address=request.remote_addr)
        db.session.add(audit)
        db.session.commit()

        from excel_service import append_order_history
        append_order_history(order, 'Created', current_user.username)

        flash(f'Order {order.order_id} created successfully!', 'success')
        return redirect(url_for('orders.list_orders'))

    return render_template('order_form.html', form=form, editing=False)


@orders_bp.route('/edit/<int:order_pk>', methods=['GET', 'POST'])
@login_required
def edit_order(order_pk):
    order = Order.query.filter_by(id=order_pk, created_by=current_user.id).first_or_404()
    form = OrderForm(obj=order)

    if form.validate_on_submit():
        new_total = form.total_quantity.data
        if new_total < (order.completed_quantity + order.rejected_quantity):
            flash('Total quantity cannot be less than completed + rejected quantities.', 'danger')
            return render_template('order_form.html', form=form, editing=True, order=order)

        order.company_id = form.company_id.data
        order.garment_type = form.garment_type.data.strip()
        order.machine_line = form.machine_line.data.strip() if form.machine_line.data else None
        order.expected_delivery = datetime.combine(form.expected_delivery.data, datetime.min.time()).replace(
            tzinfo=timezone.utc) if form.expected_delivery.data else None
        order.total_quantity = new_total
        order.remarks = form.remarks.data.strip() if form.remarks.data else None
        order.update_status()
        db.session.commit()

        audit = AuditLog(user_id=current_user.id, username=current_user.username,
                         action='ORDER_UPDATED',
                         details=f'Order updated: {order.order_id}',
                         ip_address=request.remote_addr)
        db.session.add(audit)
        db.session.commit()

        from excel_service import append_order_history
        append_order_history(order, 'Updated', current_user.username)

        flash(f'Order {order.order_id} updated.', 'success')
        return redirect(url_for('orders.list_orders'))

    return render_template('order_form.html', form=form, editing=True, order=order)


# ---------------------------------------------------------------------------
# Production entry routes
# ---------------------------------------------------------------------------

@orders_bp.route('/production', methods=['GET', 'POST'])
@login_required
def production_entry():
    form = ProductionForm()
    if form.validate_on_submit():
        order = Order.query.filter_by(id=form.order_id.data, created_by=current_user.id).first_or_404()
        completed = form.quantity_completed.data or 0
        rejected = form.quantity_rejected.data or 0

        if completed <= 0:
            flash('Please enter a valid return completed quantity (must be greater than 0).', 'warning')
            return render_template('production.html', form=form)

        if (order.completed_quantity + completed + order.rejected_quantity + rejected) > order.total_quantity:
            flash(
                f'Cannot exceed total quantity ({order.total_quantity}). '
                f'Already completed: {order.completed_quantity}, rejected: {order.rejected_quantity}. '
                f'Maximum you can enter: {order.remaining_quantity}.',
                'danger'
            )
            return render_template('production.html', form=form)

        entry = ProductionEntry(
            entry_id=_generate_entry_id(current_user.id),
            order_id=order.id,
            quantity_completed=completed,
            quantity_rejected=rejected,
            remarks=form.remarks.data.strip() if form.remarks.data else None,
            entered_by=current_user.id
        )
        order.completed_quantity += completed
        order.rejected_quantity += rejected
        order.update_status()

        db.session.add(entry)
        db.session.commit()

        audit = AuditLog(user_id=current_user.id, username=current_user.username,
                         action='PRODUCTION_ENTRY',
                         details=f'Production recorded: {entry.entry_id} for {order.order_id}, '
                                 f'completed={completed}, rejected={rejected}',
                         ip_address=request.remote_addr)
        db.session.add(audit)
        db.session.commit()

        from excel_service import append_production_history
        append_production_history(entry, order, current_user.username)

        flash(f'Return entry {entry.entry_id} recorded for order {order.order_id}.', 'success')
        return redirect(url_for('orders.production_entry'))

    return render_template('production.html', form=form)


@orders_bp.route('/history')
@login_required
def production_history():
    page = request.args.get('page', 1, type=int)
    company_filter = request.args.get('company', '', type=str)
    order_filter = request.args.get('order', '', type=str)
    date_from = request.args.get('date_from', '', type=str)
    date_to = request.args.get('date_to', '', type=str)

    query = ProductionEntry.query.join(Order).join(Company).filter(Order.created_by == current_user.id)

    if company_filter:
        query = query.filter(Company.company_id == company_filter)
    if order_filter:
        query = query.filter(Order.order_id == order_filter)
    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            query = query.filter(ProductionEntry.entry_date >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            query = query.filter(ProductionEntry.entry_date <= dt)
        except ValueError:
            pass

    entries = query.order_by(ProductionEntry.entry_date.desc()).paginate(page=page, per_page=20, error_out=False)
    companies = Company.query.filter_by(created_by=current_user.id).order_by(Company.company_name).all()
    orders_list = Order.query.filter_by(created_by=current_user.id).order_by(Order.order_id.desc()).all()

    return render_template('history.html', entries=entries, companies=companies, orders_list=orders_list,
                           company_filter=company_filter, order_filter=order_filter,
                           date_from=date_from, date_to=date_to)


@orders_bp.route('/view/<int:order_pk>')
@login_required
def view_order(order_pk):
    order = Order.query.filter_by(id=order_pk, created_by=current_user.id).first_or_404()
    entries = order.production_entries.all()
    return render_template('order_view.html', order=order, entries=entries)
