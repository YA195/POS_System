"""Invoice management views."""
from flask import Blueprint, render_template, request, jsonify
from controllers.invoice_controller import InvoiceController
from models.trader import Trader
from utils.auth import login_required, permission_required

invoice_bp = Blueprint('invoices', __name__)


@invoice_bp.route('/invoice')
@login_required
@permission_required('invoices')
def invoice():
    """Render invoice creation page."""
    return render_template('invoice.html')


@invoice_bp.route('/invoices')
@login_required
@permission_required('invoices')
def invoices():
    """Render invoices list page."""
    return render_template('invoices.html')


@invoice_bp.route('/get_invoices')
@login_required
def get_invoices():
    """Get all invoices."""
    try:
        from models.invoice import Invoice
        invoices = Invoice.get_all()
        return jsonify({'success': True, 'invoices': invoices})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@invoice_bp.route('/save_invoice', methods=['POST'])
@login_required
@permission_required('invoices')
def save_invoice():
    """Create a new invoice."""
    try:
        data = request.get_json()
        
        invoice_data = {
            'trader_id': data['trader_id'],
            'total_amount': data['total_amount'],
            'paid_amount': data.get('paid_amount', 0),
        }
        
        items = data.get('items', [])
        
        invoice_id = InvoiceController.create_invoice(invoice_data, items)
        
        return jsonify({
            'success': True,
            'invoice_id': invoice_id,
            'message': 'Invoice created successfully'
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@invoice_bp.route('/get_invoice_details/<int:invoice_id>')
@login_required
def get_invoice_details(invoice_id):
    """Get invoice details with items."""
    try:
        invoice_details = InvoiceController.get_invoice_details(invoice_id)
        
        if invoice_details:
            return jsonify({'success': True, 'invoice': invoice_details})
        else:
            return jsonify({'success': False, 'message': 'Invoice not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@invoice_bp.route('/process_payment', methods=['POST'])
@login_required
@permission_required('invoices')
def process_payment():
    """Process payment for an invoice."""
    try:
        data = request.get_json()
        invoice_id = data['invoice_id']
        amount = data['amount']
        
        InvoiceController.process_payment(invoice_id, amount)
        
        return jsonify({
            'success': True,
            'message': 'Payment processed successfully'
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@invoice_bp.route('/traders')
@login_required
@permission_required('invoices')
def traders():
    """Render traders/suppliers page."""
    try:
        from database.db import get_db
        conn = get_db()
        cursor = conn.cursor()
        
        # Get companies for the dropdown
        cursor.execute("SELECT id, name FROM companies WHERE ISNULL(active, 1) = 1 ORDER BY name")
        companies_data = cursor.fetchall()
        
        companies = [{
            'id': row[0],
            'name': row[1]
        } for row in companies_data]
        
        return render_template('traders.html', companies=companies)
    except Exception as e:
        print(f"Error loading traders page: {e}")
        return render_template('traders.html', companies=[])


@invoice_bp.route('/get_traders')
@login_required
def get_traders():
    """Get all traders."""
    try:
        from database.db import get_db
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.id, t.name, t.phone, t.company, t.days, c.name as company_name
            FROM traders t
            LEFT JOIN companies c ON t.company = c.id
            WHERE ISNULL(t.active, 1) = 1
            ORDER BY t.name
        """)
        traders_data = cursor.fetchall()
        
        traders = [{
            'id': row[0],
            'name': row[1],
            'phone': row[2] or '',
            'company': row[3],
            'days': row[4] or '',
            'company_name': row[5] or ''
        } for row in traders_data]
        
        return jsonify(traders)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@invoice_bp.route('/save_trader', methods=['POST'])
@login_required
@permission_required('invoices')
def save_trader():
    """Create a new trader."""
    try:
        from database.db import get_db
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO traders (name, phone, company, days, active) 
            VALUES (?, ?, ?, ?, 1)
        """, [data['name'], data.get('phone', ''), data.get('company'), data.get('days', '')])
        conn.commit()
        
        trader_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
        return jsonify({'success': True, 'trader_id': trader_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@invoice_bp.route('/update_trader/<int:trader_id>', methods=['PUT'])
@login_required
@permission_required('invoices')
def update_trader(trader_id):
    """Update an existing trader."""
    try:
        from database.db import get_db
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE traders 
            SET name = ?, phone = ?, company = ?, days = ?
            WHERE id = ?
        """, [data['name'], data.get('phone', ''), data.get('company'), data.get('days', ''), trader_id])
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@invoice_bp.route('/delete_trader/<int:trader_id>', methods=['DELETE'])
@login_required
@permission_required('invoices')
def delete_trader(trader_id):
    """Delete a trader."""
    try:
        from database.db import get_db
        conn = get_db()
        cursor = conn.cursor()
        
        # Soft delete by setting active = 0
        cursor.execute("UPDATE traders SET active = 0 WHERE id = ?", [trader_id])
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@invoice_bp.route('/supplier_balances')
@login_required
@permission_required('invoices')
def supplier_balances():
    """Render supplier balances page."""
    return render_template('supplier_balances.html')


@invoice_bp.route('/get_supplier_balances')
@login_required
def get_supplier_balances():
    """Get supplier balance report."""
    try:
        from controllers.report_controller import ReportController
        balances = ReportController.get_supplier_balance_report()
        return jsonify({'success': True, 'balances': balances})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
