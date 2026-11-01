"""
Excel history service — appends business records to .xlsx workbooks
and provides download / reporting helpers.
"""

import os
import shutil
import threading
from datetime import datetime, timezone

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from flask import current_app

# Module-level lock to prevent concurrent writes
_excel_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Header styles
# ---------------------------------------------------------------------------

_HEADER_FONT = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
_HEADER_FILL = PatternFill(start_color='2C3E50', end_color='2C3E50', fill_type='solid')
_HEADER_ALIGN = Alignment(horizontal='center', vertical='center', wrap_text=True)
_THIN_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)

COMPANY_HEADERS = [
    'Entry ID', 'Timestamp', 'Action', 'Company ID', 'Company Name',
    'Contact Person', 'Phone', 'Address', 'Remarks', 'Updated By'
]

ORDER_HEADERS = [
    'Entry ID', 'Timestamp', 'Action', 'Order ID', 'Company ID', 'Company Name',
    'Garment Type', 'Machine/Line', 'Order Date', 'Expected Delivery',
    'Total Qty', 'Completed Qty', 'Rejected Qty', 'Remaining Qty',
    'Status', 'Remarks', 'Updated By'
]

PRODUCTION_HEADERS = [
    'Entry ID', 'Timestamp', 'Production Entry ID', 'Order ID',
    'Company ID', 'Company Name', 'Garment Type',
    'Qty Completed', 'Qty Rejected', 'Running Completed', 'Running Rejected',
    'Remaining Qty', 'Remarks', 'Entered By'
]


# ---------------------------------------------------------------------------
# Workbook initialisation helpers
# ---------------------------------------------------------------------------

def _ensure_dirs():
    """Create the excel_data and backups directories if they don't exist."""
    excel_dir = current_app.config['EXCEL_DIR']
    backup_dir = current_app.config['BACKUP_DIR']
    os.makedirs(excel_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)


def _style_headers(ws, headers):
    """Write and style the header row."""
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _HEADER_ALIGN
        cell.border = _THIN_BORDER
    ws.freeze_panes = 'A2'


def _get_or_create_workbook(filename, headers):
    """Load an existing workbook or create a new one with headers."""
    _ensure_dirs()
    filepath = os.path.join(current_app.config['EXCEL_DIR'], filename)
    if os.path.exists(filepath):
        try:
            wb = load_workbook(filepath)
            return wb, filepath
        except Exception:
            # Corrupted file — back up and recreate
            _backup_file(filepath)
    wb = Workbook()
    ws = wb.active
    ws.title = 'History'
    _style_headers(ws, headers)
    # Set reasonable column widths
    for col_idx in range(1, len(headers) + 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = 18
    wb.save(filepath)
    return wb, filepath


def _next_entry_id(ws, prefix):
    """Generate a sequential entry ID for the Excel sheet."""
    max_row = ws.max_row
    return f'{prefix}-{max_row:06d}'


def _backup_file(filepath):
    """Create a timestamped backup of an Excel file."""
    if not os.path.exists(filepath):
        return
    backup_dir = current_app.config['BACKUP_DIR']
    os.makedirs(backup_dir, exist_ok=True)
    basename = os.path.basename(filepath)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'{ts}_{basename}')
    try:
        shutil.copy2(filepath, backup_path)
    except Exception:
        pass


def _safe_save(wb, filepath):
    """Save workbook with backup on failure."""
    try:
        wb.save(filepath)
    except PermissionError:
        # File might be open — save to a temp path
        temp_path = filepath + '.tmp'
        wb.save(temp_path)
        raise


# ---------------------------------------------------------------------------
# Append functions
# ---------------------------------------------------------------------------

def append_company_history(company, action, username):
    """Append a company event row to Company_History.xlsx."""
    with _excel_lock:
        try:
            wb, filepath = _get_or_create_workbook('Company_History.xlsx', COMPANY_HEADERS)
            ws = wb.active
            entry_id = _next_entry_id(ws, 'CH')
            now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            ws.append([
                entry_id, now, action,
                company.company_id, company.company_name,
                company.contact_person or '', company.phone or '',
                company.address or '', company.remarks or '',
                username
            ])
            _safe_save(wb, filepath)
        except Exception as e:
            current_app.logger.error(f'Excel write error (company): {e}')


def append_order_history(order, action, username):
    """Append an order event row to Order_History.xlsx."""
    with _excel_lock:
        try:
            wb, filepath = _get_or_create_workbook('Order_History.xlsx', ORDER_HEADERS)
            ws = wb.active
            entry_id = _next_entry_id(ws, 'OH')
            now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            company = order.company if hasattr(order, 'company') and order.company else None
            company_id_str = company.company_id if company else ''
            company_name = company.company_name if company else ''

            ws.append([
                entry_id, now, action,
                order.order_id, company_id_str, company_name,
                order.garment_type, order.machine_line or '',
                order.order_date.strftime('%Y-%m-%d') if order.order_date else '',
                order.expected_delivery.strftime('%Y-%m-%d') if order.expected_delivery else '',
                order.total_quantity, order.completed_quantity,
                order.rejected_quantity, order.remaining_quantity,
                order.status, order.remarks or '',
                username
            ])
            _safe_save(wb, filepath)
        except Exception as e:
            current_app.logger.error(f'Excel write error (order): {e}')


def append_production_history(entry, order, username):
    """Append a production entry row to Production_History.xlsx."""
    with _excel_lock:
        try:
            wb, filepath = _get_or_create_workbook('Production_History.xlsx', PRODUCTION_HEADERS)
            ws = wb.active
            eid = _next_entry_id(ws, 'PH')
            now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

            company = order.company if hasattr(order, 'company') and order.company else None
            company_id_str = company.company_id if company else ''
            company_name = company.company_name if company else ''

            ws.append([
                eid, now, entry.entry_id, order.order_id,
                company_id_str, company_name, order.garment_type,
                entry.quantity_completed, entry.quantity_rejected,
                order.completed_quantity, order.rejected_quantity,
                order.remaining_quantity, entry.remarks or '',
                username
            ])
            _safe_save(wb, filepath)
        except Exception as e:
            current_app.logger.error(f'Excel write error (production): {e}')


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_filtered_report(user_id=None, company_id=None, order_id=None, date_from=None, date_to=None):
    """
    Generate a filtered Excel report workbook (in memory) from production history.
    Returns a Workbook object.
    """
    from models import ProductionEntry, Order, Company

    query = ProductionEntry.query.join(Order).join(Company)

    if user_id:
        query = query.filter(Order.created_by == user_id)
    if company_id:
        query = query.filter(Company.company_id == company_id)
    if order_id:
        query = query.filter(Order.order_id == order_id)
    if date_from:
        query = query.filter(ProductionEntry.entry_date >= date_from)
    if date_to:
        query = query.filter(ProductionEntry.entry_date <= date_to)

    entries = query.order_by(ProductionEntry.entry_date.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = 'Production Report'

    headers = [
        'Entry ID', 'Date', 'Order ID', 'Company', 'Garment Type',
        'Qty Completed', 'Qty Rejected', 'Total Completed', 'Total Rejected',
        'Remaining', 'Remarks', 'Entered By'
    ]
    _style_headers(ws, headers)

    for e in entries:
        order = e.order
        company = order.company
        user = e.user
        ws.append([
            e.entry_id,
            e.entry_date.strftime('%Y-%m-%d %H:%M') if e.entry_date else '',
            order.order_id,
            company.company_name if company else '',
            order.garment_type,
            e.quantity_completed, e.quantity_rejected,
            order.completed_quantity, order.rejected_quantity,
            order.remaining_quantity,
            e.remarks or '',
            user.username if user else ''
        ])

    for col_idx in range(1, len(headers) + 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = 18

    return wb


def export_user_history(user_id, filetype):
    """
    Export a user-isolated history Excel workbook.
    Returns a Workbook object.
    """
    from models import Company, Order, ProductionEntry

    wb = Workbook()
    ws = wb.active

    if filetype == 'company':
        ws.title = 'Company History'
        _style_headers(ws, COMPANY_HEADERS)
        companies = Company.query.filter_by(created_by=user_id).order_by(Company.registration_date.desc()).all()
        for idx, c in enumerate(companies, 1):
            ws.append([
                f'CH-{idx:04d}',
                c.registration_date.strftime('%Y-%m-%d %H:%M') if c.registration_date else '',
                'Active' if c.is_active else 'Inactive',
                c.company_id,
                c.company_name,
                c.contact_person or '',
                c.phone or '',
                c.address or '',
                c.remarks or '',
                c.created_by
            ])
        headers = COMPANY_HEADERS

    elif filetype == 'order':
        ws.title = 'Order History'
        _style_headers(ws, ORDER_HEADERS)
        orders = Order.query.filter_by(created_by=user_id).order_by(Order.order_date.desc()).all()
        for idx, o in enumerate(orders, 1):
            ws.append([
                f'OH-{idx:04d}',
                o.order_date.strftime('%Y-%m-%d %H:%M') if o.order_date else '',
                'Active',
                o.order_id,
                o.company.company_id if o.company else '',
                o.company.company_name if o.company else '',
                o.garment_type,
                o.machine_line or '',
                o.order_date.strftime('%Y-%m-%d') if o.order_date else '',
                o.expected_delivery.strftime('%Y-%m-%d') if o.expected_delivery else '',
                o.total_quantity,
                o.completed_quantity,
                o.rejected_quantity,
                o.remaining_quantity,
                o.status,
                o.remarks or '',
                o.created_by
            ])
        headers = ORDER_HEADERS

    elif filetype == 'production':
        ws.title = 'Production History'
        _style_headers(ws, PRODUCTION_HEADERS)
        entries = (ProductionEntry.query
                   .join(Order)
                   .filter(Order.created_by == user_id)
                   .order_by(ProductionEntry.entry_date.desc()).all())
        for idx, e in enumerate(entries, 1):
            o = e.order
            c = o.company if o else None
            ws.append([
                f'PH-{idx:04d}',
                e.entry_date.strftime('%Y-%m-%d %H:%M') if e.entry_date else '',
                e.entry_id,
                o.order_id if o else '',
                c.company_id if c else '',
                c.company_name if c else '',
                o.garment_type if o else '',
                e.quantity_completed,
                e.quantity_rejected,
                o.completed_quantity if o else 0,
                o.rejected_quantity if o else 0,
                o.remaining_quantity if o else 0,
                e.remarks or '',
                e.user.username if e.user else ''
            ])
        headers = PRODUCTION_HEADERS

    else:
        return None

    for col_idx in range(1, len(headers) + 1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = 18

    return wb


def create_backup():
    """Create timestamped backups of all Excel workbooks."""
    _ensure_dirs()
    excel_dir = current_app.config['EXCEL_DIR']
    for filename in ['Company_History.xlsx', 'Order_History.xlsx', 'Production_History.xlsx']:
        filepath = os.path.join(excel_dir, filename)
        _backup_file(filepath)


def init_excel_workbooks():
    """Initialize all Excel workbooks if they don't exist."""
    _ensure_dirs()
    _get_or_create_workbook('Company_History.xlsx', COMPANY_HEADERS)
    _get_or_create_workbook('Order_History.xlsx', ORDER_HEADERS)
    _get_or_create_workbook('Production_History.xlsx', PRODUCTION_HEADERS)
