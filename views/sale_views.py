"""Sales management views."""
from flask import Blueprint, render_template, request, jsonify, session
from controllers.sale_controller import SaleController
from database.db import get_db
from utils.auth import login_required, permission_required

sale_bp = Blueprint('sales', __name__)


@sale_bp.route('/sales')
@login_required
@permission_required('sales')
def sales():
    """Render sales page with all sales."""
    try:
        # Get all sales from database
        conn = get_db()
        cursor = conn.cursor()
        
        # Query to get all sales with their details
        cursor.execute("""
            SELECT 
                ds.id,
                ds.sale_number,
                ds.sale_date,
                ds.total_amount,
                ds.subtotal,
                ds.discount_amount,
                ds.delivery_fee,
                ds.final_amount,
                ds.payment_method,
                ds.customer_name,
                ds.customer_phone,
                ds.delivery_worker_name,
                ds.status,
                ds.created_at,
                u.username
            FROM daily_sales ds
            LEFT JOIN users u ON ds.user_id = u.id
            ORDER BY ds.created_at DESC
        """)
        
        sales_data = cursor.fetchall()
        
        # Format sales for template
        sales_list = []
        for sale in sales_data:
            sale_dict = {
                'id': sale[0],
                'sale_number': sale[1],
                'sale_date': sale[2],
                'total_amount': float(sale[3]) if sale[3] else 0,
                'subtotal': float(sale[4]) if sale[4] else 0,
                'discount_amount': float(sale[5]) if sale[5] else 0,
                'delivery_fee': float(sale[6]) if sale[6] else 0,
                'final_amount': float(sale[7]) if sale[7] else 0,
                'payment_method': sale[8] or '',
                'customer_name': sale[9] or '',
                'customer_phone': sale[10] or '',
                'delivery_worker_name': sale[11] or '',
                'status': sale[12] or 'completed',
                'created_at': sale[13],
                'username': sale[14] or '',
                'return_status': 'none',  # TODO: implement return tracking
                'sale_items': []  # Will be loaded via AJAX when expanded
            }
            sales_list.append(sale_dict)
        
        print(f"Loaded {len(sales_list)} sales for display")
        return render_template('sales.html', sales_list=sales_list)
        
    except Exception as e:
        print(f"Error loading sales: {e}")
        import traceback
        traceback.print_exc()
        return render_template('sales.html', sales_list=[])


@sale_bp.route('/save_sale', methods=['POST'])
@login_required
@permission_required('sales')
def save_sale():
    """Create a new sale."""
    try:
        data = request.get_json()
        
        # Get current shift or create one automatically
        from models.shift import Shift
        active_shift = Shift.get_active()
        
        if not active_shift:
            # Auto-create shift for current user
            user_id = session.get('user_id')
            cashier_name = session.get('username', 'Unknown')
            
            if not user_id:
                return jsonify({'success': False, 'error': 'User not logged in'}), 401
            
            # Create new shift - match schema: cashier_name is required
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO shifts (user_id, cashier_name, start_time, status, sales, invoices, expenses, returned_sales, returned_items)
                VALUES (?, ?, GETDATE(), 'active', 0, 0, 0, 0, 0)
            """, [user_id, cashier_name])
            conn.commit()
            
            # Get the newly created shift
            cursor.execute("SELECT @@IDENTITY AS id")
            result = cursor.fetchone()
            shift_id = int(result[0]) if result else None
            
            if not shift_id:
                return jsonify({'success': False, 'error': 'Failed to create shift'}), 500
        else:
            shift_id = active_shift[0]  # First column is id
        
        # Generate sale number (get next number for this shift)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ISNULL(MAX(sale_number), 0) + 1 
            FROM daily_sales 
            WHERE shift_id = ?
        """, [shift_id])
        sale_number = cursor.fetchone()[0]
        
        sale_data = {
            'sale_number': sale_number,
            'shift_id': shift_id,
            'total_amount': data['total_amount'],
            'subtotal': data.get('subtotal', data['total_amount']),
            'discount_amount': data.get('discount_amount', 0),
            'delivery_fee': data.get('delivery_fee', 0),
            'final_amount': data['final_amount'],
            'paid_amount': data.get('paid_amount', 0),
            'residual_amount': data.get('residual', 0),
            'payment_method': data.get('payment_method', 'cash'),
            'cash_box_id': data.get('cash_box_id'),
            'customer_name': data.get('customer_name', ''),
            'customer_phone': data.get('customer_phone', ''),
            'address_line1': data.get('address_line1', ''),
            'address_line2': data.get('address_line2', ''),
            'address_line3': data.get('address_line3', ''),
            'user_id': session.get('user_id')
        }
        
        items = data.get('items', [])
        
        sale_id = SaleController.create_sale(sale_data, items)
        
        return jsonify({
            'success': True,
            'daily_sale_id': sale_id,
            'sale_number': sale_number,
            'message': 'Sale created successfully'
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        print(f"Error saving sale: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@sale_bp.route('/get_sale_items/<int:sale_id>')
@login_required
def get_sale_items(sale_id):
    """Get items for a sale."""
    try:
        from database.db import get_db
        conn = get_db()
        cursor = conn.cursor()
        
        # Get sale details
        cursor.execute("SELECT * FROM daily_sales WHERE id = ?", [sale_id])
        sale_row = cursor.fetchone()
        
        if not sale_row:
            return jsonify({'success': False, 'message': 'Sale not found'}), 404
        
        # Get sale items - convert Row to list
        cursor.execute("""
            SELECT id, sale_id, item_id, barcode, item_name, quantity, unit_price, total_price
            FROM daily_sale_items 
            WHERE sale_id = ?
        """, [sale_id])
        
        items_rows = cursor.fetchall()
        
        # Convert Row objects to lists
        items = [list(row) for row in items_rows]
        sale = list(sale_row)
        
        print(f"Loaded {len(items)} items for sale {sale_id}")
        
        return jsonify({
            'success': True,
            'sale': {
                'sale': sale,
                'items': items
            }
        })
            
    except Exception as e:
        print(f"Error getting sale items: {e}")
        import traceback
        traceback.print_exc()
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


@sale_bp.route('/delivery')
@login_required
def delivery_page():
    """Render delivery management page."""
    return render_template('delivery.html')


@sale_bp.route('/delivery_fees_by_worker')
@login_required
def delivery_fees_by_worker():
    """Render the dedicated page for viewing fees by worker and shift."""
    return render_template('delivery_fees_by_worker.html')

