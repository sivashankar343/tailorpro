"""
Billing and Tax Invoice blueprint for TailorPro.
Supports manual invoice numbering, manual product items, manual rates, GST rates,
and renders authentic GST tax invoices matching the standard Indian format.
"""

from datetime import datetime, date, timezone
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import login_required, current_user
from models import db, Invoice, InvoiceItem, Company, AuditLog

billing_bp = Blueprint('billing', __name__, url_prefix='/invoices')


def number_to_indian_words(num):
    """Convert a numeric currency value into Indian English words."""
    if num is None:
        return ""
    try:
        num = round(float(num), 2)
    except (ValueError, TypeError):
        return ""

    if num == 0:
        return "Zero Rupees Only /-"

    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def two_digits(n):
        if n < 20:
            return ones[n]
        return tens[n // 10] + (" " + ones[n % 10] if n % 10 != 0 else "")

    def three_digits(n):
        h = n // 100
        rem = n % 100
        res = ""
        if h > 0:
            res += ones[h] + " Hundred"
            if rem > 0:
                res += " "
        if rem > 0:
            res += two_digits(rem)
        return res.strip()

    rupees = int(num)
    paise = int(round((num - rupees) * 100))

    crores = rupees // 10000000
    rupees %= 10000000
    lakhs = rupees // 100000
    rupees %= 100000
    thousands = rupees // 1000
    rupees %= 1000
    hundreds = rupees

    parts = []
    if crores > 0:
        parts.append(two_digits(crores) + " Crore")
    if lakhs > 0:
        parts.append(two_digits(lakhs) + " Lakh")
    if thousands > 0:
        parts.append(two_digits(thousands) + " Thousand")
    if hundreds > 0:
        parts.append(three_digits(hundreds))

    rupee_str = " ".join(parts).strip()
    if not rupee_str:
        rupee_str = "Zero"

    res = rupee_str + " Rupees"
    if paise > 0:
        res += " and " + two_digits(paise) + " Paise"
    res += " Only /-"
    return res


@billing_bp.route('/')
@login_required
def list_invoices():
    """List all tax invoices for the current user."""
    invoices = Invoice.query.filter_by(created_by=current_user.id).order_by(Invoice.created_at.desc()).all()
    return render_template('invoices.html', invoices=invoices)


@billing_bp.route('/api/company/<int:company_id>')
@login_required
def get_company_details(company_id):
    """Fetch company details for auto-populating buyer fields."""
    comp = Company.query.filter_by(id=company_id, created_by=current_user.id).first()
    if not comp:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'company_name': comp.company_name,
        'address': comp.address or '',
        'phone': comp.phone or '',
    })


@billing_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_invoice():
    """Create a new manual tax invoice."""
    # Find last used seller details for current user to pre-fill convenience
    last_inv = Invoice.query.filter_by(created_by=current_user.id).order_by(Invoice.id.desc()).first()
    
    default_seller_name = last_inv.seller_name if last_inv else "SRI AGATHESWARAR MECHANICAL WORKS"
    default_seller_addr = last_inv.seller_address if last_inv else "176/338 KUMAR NAGAR MAIN ROAD,VALAYANKADU ROAD, TIRUPUR, Tiruppur, Tamil Nadu, 641603"
    default_seller_gstin = last_inv.seller_gstin if last_inv else "33BCJPS4966H1Z5"
    default_seller_state_code = last_inv.seller_state_code if last_inv else "33"
    
    # Auto-suggested next invoice number (e.g. 1, 2, or max+1, but user can freely edit)
    suggested_inv_no = "1"
    if last_inv and last_inv.invoice_number.isdigit():
        suggested_inv_no = str(int(last_inv.invoice_number) + 1)
    elif last_inv:
        suggested_inv_no = f"{last_inv.invoice_number}-1"

    if request.method == 'POST':
        inv_no = request.form.get('invoice_number', '').strip()
        if not inv_no:
            flash('Invoice number is required.', 'danger')
            return redirect(url_for('billing.new_invoice'))

        # Check unique constraint for this user
        existing = Invoice.query.filter_by(created_by=current_user.id, invoice_number=inv_no).first()
        if existing:
            flash(f'Invoice number "{inv_no}" already exists in your account. Please use a unique number.', 'danger')
            return redirect(url_for('billing.new_invoice'))

        inv_date_str = request.form.get('invoice_date', '')
        try:
            inv_date = datetime.strptime(inv_date_str, '%Y-%m-%d').date() if inv_date_str else date.today()
        except ValueError:
            inv_date = date.today()

        # Consignee / Shipped to
        same_as_billing = request.form.get('same_as_billing') == 'on'
        buyer_name = request.form.get('buyer_name', '').strip()
        buyer_address = request.form.get('buyer_address', '').strip()
        buyer_gstin = request.form.get('buyer_gstin', '').strip()
        buyer_state_code = request.form.get('buyer_state_code', '33').strip()
        buyer_state = request.form.get('buyer_state', 'Tamil Nadu').strip()

        if same_as_billing:
            ship_name = buyer_name
            ship_address = buyer_address
            ship_gstin = buyer_gstin
            ship_state_code = buyer_state_code
            ship_state = buyer_state
        else:
            ship_name = request.form.get('ship_name', '').strip() or buyer_name
            ship_address = request.form.get('ship_address', '').strip() or buyer_address
            ship_gstin = request.form.get('ship_gstin', '').strip() or buyer_gstin
            ship_state_code = request.form.get('ship_state_code', buyer_state_code).strip()
            ship_state = request.form.get('ship_state', buyer_state).strip()

        invoice = Invoice(
            created_by=current_user.id,
            invoice_number=inv_no,
            invoice_date=inv_date,
            state=request.form.get('state', 'Tamil Nadu').strip(),
            reverse_charge=request.form.get('reverse_charge', 'NO').strip(),
            seller_name=request.form.get('seller_name', '').strip(),
            seller_address=request.form.get('seller_address', '').strip(),
            seller_gstin=request.form.get('seller_gstin', '').strip(),
            seller_state_code=request.form.get('seller_state_code', '33').strip(),
            buyer_name=buyer_name,
            buyer_address=buyer_address,
            buyer_gstin=buyer_gstin,
            buyer_state_code=buyer_state_code,
            buyer_state=buyer_state,
            ship_name=ship_name,
            ship_address=ship_address,
            ship_gstin=ship_gstin,
            ship_state_code=ship_state_code,
            ship_state=ship_state,
            terms_conditions=request.form.get('terms_conditions', '1. This is an electronically generated document. 2. All disputes are subject to Tiruppur jurisdiction.').strip()
        )

        db.session.add(invoice)
        db.session.flush()

        # Parse line items
        product_names = request.form.getlist('product_name[]')
        quantities = request.form.getlist('quantity[]')
        units = request.form.getlist('unit[]')
        rates = request.form.getlist('rate[]')
        taxable_values = request.form.getlist('taxable_value[]')
        cgst_rates = request.form.getlist('cgst_rate[]')
        sgst_rates = request.form.getlist('sgst_rate[]')
        gst_rates = request.form.getlist('gst_rate[]')

        total_qty = 0.0
        total_taxable_value = 0.0
        total_cgst = 0.0
        total_sgst = 0.0
        grand_total = 0.0

        for idx, p_name in enumerate(product_names):
            p_name = p_name.strip()
            if not p_name:
                continue

            try:
                qty = float(quantities[idx]) if idx < len(quantities) and quantities[idx] else 1.0
            except ValueError:
                qty = 1.0

            unit = units[idx].strip() if idx < len(units) else ''

            try:
                rate = float(rates[idx]) if idx < len(rates) and rates[idx] else 0.0
            except ValueError:
                rate = 0.0

            try:
                if idx < len(taxable_values) and taxable_values[idx]:
                    taxable_val = float(taxable_values[idx])
                else:
                    taxable_val = round(qty * rate, 2)
            except ValueError:
                taxable_val = round(qty * rate, 2)

            try:
                if idx < len(cgst_rates) and cgst_rates[idx] != '':
                    cgst_pct = float(cgst_rates[idx])
                elif idx < len(gst_rates) and gst_rates[idx]:
                    cgst_pct = float(gst_rates[idx]) / 2.0
                else:
                    cgst_pct = 9.0
            except ValueError:
                cgst_pct = 9.0

            try:
                if idx < len(sgst_rates) and sgst_rates[idx] != '':
                    sgst_pct = float(sgst_rates[idx])
                elif idx < len(gst_rates) and gst_rates[idx]:
                    sgst_pct = float(gst_rates[idx]) / 2.0
                else:
                    sgst_pct = 9.0
            except ValueError:
                sgst_pct = 9.0

            cgst_amt = round(taxable_val * (cgst_pct / 100.0), 2)
            sgst_amt = round(taxable_val * (sgst_pct / 100.0), 2)
            item_total = round(taxable_val + cgst_amt + sgst_amt, 2)

            item = InvoiceItem(
                invoice_id=invoice.id,
                item_index=idx + 1,
                product_name=p_name,
                quantity=qty,
                unit=unit,
                rate=rate,
                taxable_value=taxable_val,
                cgst_rate=cgst_pct,
                cgst_amount=cgst_amt,
                sgst_rate=sgst_pct,
                sgst_amount=sgst_amt,
                total_amount=item_total
            )
            db.session.add(item)

            total_qty += qty
            total_taxable_value += taxable_val
            total_cgst += cgst_amt
            total_sgst += sgst_amt
            grand_total += item_total

        invoice.total_qty = round(total_qty, 2)
        invoice.total_taxable_value = round(total_taxable_value, 2)
        invoice.total_cgst = round(total_cgst, 2)
        invoice.total_sgst = round(total_sgst, 2)
        invoice.total_tax = round(total_cgst + total_sgst, 2)
        invoice.grand_total = round(grand_total, 2)
        invoice.balance_due = round(grand_total, 2)
        invoice.amount_in_words = number_to_indian_words(grand_total)

        db.session.commit()
        flash(f'Tax Invoice #{invoice.invoice_number} generated successfully!', 'success')
        return redirect(url_for('billing.view_invoice', id=invoice.id))

    user_companies = Company.query.filter_by(created_by=current_user.id, is_active=True).all()
    today_str = date.today().strftime('%Y-%m-%d')
    return render_template('invoice_form.html',
                           invoice=None,
                           companies=user_companies,
                           default_seller_name=default_seller_name,
                           default_seller_addr=default_seller_addr,
                           default_seller_gstin=default_seller_gstin,
                           default_seller_state_code=default_seller_state_code,
                           suggested_inv_no=suggested_inv_no,
                           today_str=today_str)


@billing_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_invoice(id):
    """Edit an existing invoice."""
    invoice = Invoice.query.filter_by(id=id, created_by=current_user.id).first_or_404()

    if request.method == 'POST':
        inv_no = request.form.get('invoice_number', '').strip()
        if not inv_no:
            flash('Invoice number is required.', 'danger')
            return redirect(url_for('billing.edit_invoice', id=id))

        # Check unique constraint if changed
        if inv_no != invoice.invoice_number:
            existing = Invoice.query.filter_by(created_by=current_user.id, invoice_number=inv_no).first()
            if existing:
                flash(f'Invoice number "{inv_no}" already exists in your account.', 'danger')
                return redirect(url_for('billing.edit_invoice', id=id))

        inv_date_str = request.form.get('invoice_date', '')
        try:
            inv_date = datetime.strptime(inv_date_str, '%Y-%m-%d').date() if inv_date_str else invoice.invoice_date
        except ValueError:
            inv_date = invoice.invoice_date

        same_as_billing = request.form.get('same_as_billing') == 'on'
        buyer_name = request.form.get('buyer_name', '').strip()
        buyer_address = request.form.get('buyer_address', '').strip()
        buyer_gstin = request.form.get('buyer_gstin', '').strip()
        buyer_state_code = request.form.get('buyer_state_code', '33').strip()
        buyer_state = request.form.get('buyer_state', 'Tamil Nadu').strip()

        if same_as_billing:
            ship_name = buyer_name
            ship_address = buyer_address
            ship_gstin = buyer_gstin
            ship_state_code = buyer_state_code
            ship_state = buyer_state
        else:
            ship_name = request.form.get('ship_name', '').strip() or buyer_name
            ship_address = request.form.get('ship_address', '').strip() or buyer_address
            ship_gstin = request.form.get('ship_gstin', '').strip() or buyer_gstin
            ship_state_code = request.form.get('ship_state_code', buyer_state_code).strip()
            ship_state = request.form.get('ship_state', buyer_state).strip()

        invoice.invoice_number = inv_no
        invoice.invoice_date = inv_date
        invoice.state = request.form.get('state', 'Tamil Nadu').strip()
        invoice.reverse_charge = request.form.get('reverse_charge', 'NO').strip()
        invoice.seller_name = request.form.get('seller_name', '').strip()
        invoice.seller_address = request.form.get('seller_address', '').strip()
        invoice.seller_gstin = request.form.get('seller_gstin', '').strip()
        invoice.seller_state_code = request.form.get('seller_state_code', '33').strip()
        invoice.buyer_name = buyer_name
        invoice.buyer_address = buyer_address
        invoice.buyer_gstin = buyer_gstin
        invoice.buyer_state_code = buyer_state_code
        invoice.buyer_state = buyer_state
        invoice.ship_name = ship_name
        invoice.ship_address = ship_address
        invoice.ship_gstin = ship_gstin
        invoice.ship_state_code = ship_state_code
        invoice.ship_state = ship_state
        invoice.terms_conditions = request.form.get('terms_conditions', '').strip()

        # Remove old items and replace
        InvoiceItem.query.filter_by(invoice_id=invoice.id).delete()

        product_names = request.form.getlist('product_name[]')
        quantities = request.form.getlist('quantity[]')
        units = request.form.getlist('unit[]')
        rates = request.form.getlist('rate[]')
        taxable_values = request.form.getlist('taxable_value[]')
        cgst_rates = request.form.getlist('cgst_rate[]')
        sgst_rates = request.form.getlist('sgst_rate[]')
        gst_rates = request.form.getlist('gst_rate[]')

        total_qty = 0.0
        total_taxable_value = 0.0
        total_cgst = 0.0
        total_sgst = 0.0
        grand_total = 0.0

        for idx, p_name in enumerate(product_names):
            p_name = p_name.strip()
            if not p_name:
                continue

            try:
                qty = float(quantities[idx]) if idx < len(quantities) and quantities[idx] else 1.0
            except ValueError:
                qty = 1.0

            unit = units[idx].strip() if idx < len(units) else ''

            try:
                rate = float(rates[idx]) if idx < len(rates) and rates[idx] else 0.0
            except ValueError:
                rate = 0.0

            try:
                if idx < len(taxable_values) and taxable_values[idx]:
                    taxable_val = float(taxable_values[idx])
                else:
                    taxable_val = round(qty * rate, 2)
            except ValueError:
                taxable_val = round(qty * rate, 2)

            try:
                if idx < len(cgst_rates) and cgst_rates[idx] != '':
                    cgst_pct = float(cgst_rates[idx])
                elif idx < len(gst_rates) and gst_rates[idx]:
                    cgst_pct = float(gst_rates[idx]) / 2.0
                else:
                    cgst_pct = 9.0
            except ValueError:
                cgst_pct = 9.0

            try:
                if idx < len(sgst_rates) and sgst_rates[idx] != '':
                    sgst_pct = float(sgst_rates[idx])
                elif idx < len(gst_rates) and gst_rates[idx]:
                    sgst_pct = float(gst_rates[idx]) / 2.0
                else:
                    sgst_pct = 9.0
            except ValueError:
                sgst_pct = 9.0

            cgst_amt = round(taxable_val * (cgst_pct / 100.0), 2)
            sgst_amt = round(taxable_val * (sgst_pct / 100.0), 2)
            item_total = round(taxable_val + cgst_amt + sgst_amt, 2)

            item = InvoiceItem(
                invoice_id=invoice.id,
                item_index=idx + 1,
                product_name=p_name,
                quantity=qty,
                unit=unit,
                rate=rate,
                taxable_value=taxable_val,
                cgst_rate=cgst_pct,
                cgst_amount=cgst_amt,
                sgst_rate=sgst_pct,
                sgst_amount=sgst_amt,
                total_amount=item_total
            )
            db.session.add(item)

            total_qty += qty
            total_taxable_value += taxable_val
            total_cgst += cgst_amt
            total_sgst += sgst_amt
            grand_total += item_total

        invoice.total_qty = round(total_qty, 2)
        invoice.total_taxable_value = round(total_taxable_value, 2)
        invoice.total_cgst = round(total_cgst, 2)
        invoice.total_sgst = round(total_sgst, 2)
        invoice.total_tax = round(total_cgst + total_sgst, 2)
        invoice.grand_total = round(grand_total, 2)
        invoice.balance_due = round(grand_total, 2)
        invoice.amount_in_words = number_to_indian_words(grand_total)

        db.session.commit()
        flash(f'Invoice #{invoice.invoice_number} updated successfully.', 'success')
        return redirect(url_for('billing.view_invoice', id=invoice.id))

    user_companies = Company.query.filter_by(created_by=current_user.id, is_active=True).all()
    today_str = invoice.invoice_date.strftime('%Y-%m-%d')
    return render_template('invoice_form.html',
                           invoice=invoice,
                           companies=user_companies,
                           default_seller_name=invoice.seller_name,
                           default_seller_addr=invoice.seller_address,
                           default_seller_gstin=invoice.seller_gstin,
                           default_seller_state_code=invoice.seller_state_code,
                           suggested_inv_no=invoice.invoice_number,
                           today_str=today_str)


@billing_bp.route('/<int:id>')
@login_required
def view_invoice(id):
    """View and print authentic Tax Invoice matching the exact template image."""
    invoice = Invoice.query.filter_by(id=id, created_by=current_user.id).first_or_404()
    return render_template('invoice_print.html', invoice=invoice)


@billing_bp.route('/<int:id>/delete', methods=['GET', 'POST'])
@login_required
def delete_invoice(id):
    """Delete an invoice (supports both POST form and GET confirmation)."""
    invoice = Invoice.query.filter_by(id=id, created_by=current_user.id).first_or_404()
    inv_no = invoice.invoice_number
    db.session.delete(invoice)
    db.session.commit()
    flash(f'Tax Invoice #{inv_no} has been deleted successfully.', 'success')
    return redirect(url_for('billing.list_invoices'))

