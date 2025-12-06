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
    return render_template('traders.html')


@invoice_bp.route('/get_traders')
@login_required
def get_traders():
    """Get all traders."""
    try:
        traders = Trader.get_all()
        return jsonify({'success': True, 'traders': traders})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
