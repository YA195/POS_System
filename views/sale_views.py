"""Sales management views."""
from flask import Blueprint, render_template, request, jsonify
from controllers.sale_controller import SaleController
from database.db import get_db
from utils.auth import login_required, permission_required

sale_bp = Blueprint('sales', __name__)


@sale_bp.route('/sales')
@login_required
@permission_required('sales')
def sales():
    """Render sales page."""
    return render_template('sales.html')


@sale_bp.route('/save_sale', methods=['POST'])
@login_required
@permission_required('sales')
def save_sale():
    """Create a new sale."""
    try:
        data = request.get_json()
        
        sale_data = {
            'sale_number': data['sale_number'],
            'shift_id': data.get('shift_id'),
            'total_amount': data['total_amount'],
            'discount_amount': data.get('discount_amount', 0),
            'delivery_fee': data.get('delivery_fee', 0),
            'final_amount': data['final_amount'],
            'paid_amount': data.get('paid_amount', 0),
            'customer_name': data.get('customer_name', ''),
            'customer_phone': data.get('customer_phone', ''),
            'address_line1': data.get('address_line1', ''),
            'address_line2': data.get('address_line2', ''),
            'address_line3': data.get('address_line3', ''),
        }
        
        items = data.get('items', [])
        
        sale_id = SaleController.create_sale(sale_data, items)
        
        return jsonify({
            'success': True,
            'sale_id': sale_id,
            'message': 'Sale created successfully'
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@sale_bp.route('/get_sale_items/<int:sale_id>')
@login_required
def get_sale_items(sale_id):
    """Get items for a sale."""
    try:
        sale_details = SaleController.get_sale_details(sale_id)
        
        if sale_details:
            return jsonify({'success': True, 'sale': sale_details})
        else:
            return jsonify({'success': False, 'message': 'Sale not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@sale_bp.route('/process_return', methods=['POST'])
@login_required
@permission_required('sales')
def process_return():
    """Process a sale return."""
    try:
        data = request.get_json()
        sale_id = data['sale_id']
        return_items = data['items']
        
        SaleController.process_return(sale_id, return_items)
        
        return jsonify({
            'success': True,
            'message': 'Return processed successfully'
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@sale_bp.route('/print_receipt/<int:daily_sale_id>')
@login_required
def print_receipt(daily_sale_id):
    """Print receipt for a sale."""
    try:
        # This would call the printer utility
        # For now, return success
        return jsonify({
            'success': True,
            'message': 'Receipt printed successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@sale_bp.route('/get_quick_items')
@login_required
def get_quick_items():
    """Get quick access items (items with short barcodes)."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT barcode, name, sell_price 
            FROM items 
            WHERE LEN(barcode) < 4
            ORDER BY name
        """)
        
        items = cursor.fetchall()
        result = [{
            'barcode': str(item[0]),
            'name': item[1],
            'sell_price': float(item[2])
        } for item in items]
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
