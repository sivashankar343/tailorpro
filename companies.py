from datetime import datetime, timezone

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from models import db, Company, AuditLog
from auth import admin_required

companies_bp = Blueprint('companies', __name__, url_prefix='/companies')


class CompanyForm(FlaskForm):
    company_name = StringField('Company Name', validators=[DataRequired(), Length(max=200)])
    contact_person = StringField('Contact Person', validators=[Optional(), Length(max=150)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    address = TextAreaField('Address', validators=[Optional(), Length(max=500)])
    remarks = TextAreaField('Remarks', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Save Company')


def _generate_company_id(user_id):
    """Generate a unique company ID like CMP-0001 for this user."""
    count = Company.query.filter_by(created_by=user_id).count()
    return f'CMP-{count + 1:04d}'


@companies_bp.route('/')
@login_required
def list_companies():
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    query = Company.query.filter_by(created_by=current_user.id)

    if search:
        pattern = f'%{search}%'
        query = query.filter(
            Company.company_name.ilike(pattern) |
            Company.company_id.ilike(pattern) |
            Company.contact_person.ilike(pattern) |
            Company.phone.ilike(pattern)
        )

    companies = query.order_by(Company.registration_date.desc()).paginate(page=page, per_page=15, error_out=False)
    return render_template('companies.html', companies=companies, search=search)


@companies_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_company():
    form = CompanyForm()
    if form.validate_on_submit():
        company = Company(
            company_id=_generate_company_id(current_user.id),
            company_name=form.company_name.data.strip(),
            contact_person=form.contact_person.data.strip() if form.contact_person.data else None,
            phone=form.phone.data.strip() if form.phone.data else None,
            address=form.address.data.strip() if form.address.data else None,
            remarks=form.remarks.data.strip() if form.remarks.data else None,
            created_by=current_user.id
        )
        db.session.add(company)
        db.session.commit()

        # Audit log
        audit = AuditLog(user_id=current_user.id, username=current_user.username,
                         action='COMPANY_CREATED',
                         details=f'Company created: {company.company_id} - {company.company_name}',
                         ip_address=request.remote_addr)
        db.session.add(audit)
        db.session.commit()

        # Excel history
        from excel_service import append_company_history
        append_company_history(company, 'Created', current_user.username)

        flash(f'Company "{company.company_name}" added successfully!', 'success')
        return redirect(url_for('companies.list_companies'))

    return render_template('company_form.html', form=form, editing=False)


@companies_bp.route('/edit/<int:company_pk>', methods=['GET', 'POST'])
@login_required
def edit_company(company_pk):
    company = Company.query.filter_by(id=company_pk, created_by=current_user.id).first_or_404()
    form = CompanyForm(obj=company)

    if form.validate_on_submit():
        company.company_name = form.company_name.data.strip()
        company.contact_person = form.contact_person.data.strip() if form.contact_person.data else None
        company.phone = form.phone.data.strip() if form.phone.data else None
        company.address = form.address.data.strip() if form.address.data else None
        company.remarks = form.remarks.data.strip() if form.remarks.data else None
        db.session.commit()

        audit = AuditLog(user_id=current_user.id, username=current_user.username,
                         action='COMPANY_UPDATED',
                         details=f'Company updated: {company.company_id} - {company.company_name}',
                         ip_address=request.remote_addr)
        db.session.add(audit)
        db.session.commit()

        from excel_service import append_company_history
        append_company_history(company, 'Updated', current_user.username)

        flash(f'Company "{company.company_name}" updated.', 'success')
        return redirect(url_for('companies.list_companies'))

    return render_template('company_form.html', form=form, editing=True, company=company)


@companies_bp.route('/view/<int:company_pk>')
@login_required
def view_company(company_pk):
    company = Company.query.filter_by(id=company_pk, created_by=current_user.id).first_or_404()
    orders = company.orders.order_by(db.text('order_date desc')).all()
    return render_template('company_view.html', company=company, orders=orders)


@companies_bp.route('/toggle/<int:company_pk>', methods=['POST'])
@login_required
def toggle_company(company_pk):
    company = Company.query.filter_by(id=company_pk, created_by=current_user.id).first_or_404()
    company.is_active = not company.is_active
    db.session.commit()

    status = 'activated' if company.is_active else 'deactivated'
    audit = AuditLog(user_id=current_user.id, username=current_user.username,
                     action='COMPANY_TOGGLED',
                     details=f'Company {status}: {company.company_id}',
                     ip_address=request.remote_addr)
    db.session.add(audit)
    db.session.commit()

    flash(f'Company {status}.', 'info')
    return redirect(url_for('companies.list_companies'))
