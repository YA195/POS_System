"""Shift management views."""
from flask import Blueprint, render_template, request, jsonify, session
from controllers.shift_controller import ShiftController
from utils.auth import login_required, permission_required

shift_bp = Blueprint('shifts', __name__)


@shift_bp.route('/shifts')
@login_required
@permission_required('shifts')
def shifts():
    """Render shifts page."""
    try:
        shifts_data = ShiftController.get_all_shifts()
        print(f"Loaded {len(shifts_data) if shifts_data else 0} shifts from database")
        
        # Format shifts data for template
        formatted_shifts = []
        for shift in shifts_data:
            # Schema columns: id, start_time, end_time, cashier_name, sales, invoices, expenses, returned_sales, returned_items, user_id, status, username (from JOIN)
            formatted_shifts.append({
                'id': shift[0] if len(shift) > 0 else None,
                'start_time': shift[1] if len(shift) > 1 else None,
                'end_time': shift[2] if len(shift) > 2 else None,
                'cashier_name': shift[3] if len(shift) > 3 else 'Unknown',
                'sales': float(shift[4]) if len(shift) > 4 and shift[4] else 0,
                'invoices': float(shift[5]) if len(shift) > 5 and shift[5] else 0,
                'expenses': float(shift[6]) if len(shift) > 6 and shift[6] else 0,
                'returned_sales': float(shift[7]) if len(shift) > 7 and shift[7] else 0,
                'returned_items': float(shift[8]) if len(shift) > 8 and shift[8] else 0,
                'user_id': shift[9] if len(shift) > 9 else None,
                'status': shift[10] if len(shift) > 10 else 'active',
                'username': shift[11] if len(shift) > 11 else ''
            })
        
        print(f"Formatted {len(formatted_shifts)} shifts for display")
        return render_template('shifts.html', shifts=formatted_shifts)
    except Exception as e:
        print(f"Error loading shifts: {e}")
        import traceback
        traceback.print_exc()
        return render_template('shifts.html', shifts=[])


@shift_bp.route('/closing')
@login_required
@permission_required('closing')
def closing():
    """Render shift closing page."""
    return render_template('closing.html')


@shift_bp.route('/check_active_shift', methods=['GET'])
@login_required
def check_active_shift():
    """Check if there's an active shift."""
    try:
        active_shift = ShiftController.get_active_shift()
        
        if active_shift:
            return jsonify({
                'success': True,
                'has_active_shift': True,
                'shift_id': active_shift[0]
            })
        else:
            return jsonify({
                'success': True,
                'has_active_shift': False
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@shift_bp.route('/start_shift', methods=['POST'])
@login_required
@permission_required('shifts')
def start_shift():
    """Start a new shift."""
    try:
        data = request.get_json()
        opening_balance = data.get('opening_balance', 0)
        user_id = session.get('user_id')
        cashier_name = session.get('username', 'Unknown')
        
        shift_id = ShiftController.start_shift(user_id, cashier_name, opening_balance)
        
        return jsonify({
            'success': True,
            'shift_id': shift_id,
            'message': 'Shift started successfully'
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@shift_bp.route('/close_shift', methods=['POST'])
@login_required
@permission_required('closing')
def close_shift():
    """Close the active shift."""
    try:
        data = request.get_json()
        shift_id = data['shift_id']
        
        closing_data = {
            'closing_balance': data.get('closing_balance', 0),
            'total_sales': data.get('total_sales', 0),
            'total_expenses': data.get('total_expenses', 0),
        }
        
        ShiftController.close_shift(shift_id, closing_data)
        
        return jsonify({
            'success': True,
            'message': 'Shift closed successfully'
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@shift_bp.route('/get_shift_summary')
@login_required
def get_shift_summary():
    """Get summary for active shift."""
    try:
        active_shift = ShiftController.get_active_shift()
        
        if not active_shift:
            return jsonify({
                'success': False,
                'message': 'No active shift found'
            }), 404
        
        shift_id = active_shift[0]
        summary = ShiftController.get_shift_summary(shift_id)
        
        return jsonify({
            'success': True,
            'summary': summary
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@shift_bp.route('/get_shift_details/<int:shift_id>')
@login_required
def get_shift_details(shift_id):
    """Get details for a specific shift."""
    try:
        summary = ShiftController.get_shift_summary(shift_id)
        
        return jsonify({
            'success': True,
            'summary': summary
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@shift_bp.route('/get_shifts')
@login_required
def get_shifts():
    """Get all shifts."""
    try:
        shifts = ShiftController.get_all_shifts()
        return jsonify({'success': True, 'shifts': shifts})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@shift_bp.route('/get_shift_summary_shifts/<int:shift_id>')
@login_required
def get_shift_summary_shifts(shift_id):
    """Get summary for a specific shift (used by shifts.js)."""
    try:
        from database.db import get_db
        conn = get_db()
        cursor = conn.cursor()
        
        # Get shift basic info
        cursor.execute("""
            SELECT id, start_time, end_time, cashier_name, sales, invoices, expenses, returned_sales, returned_items, status
            FROM shifts
            WHERE id = ?
        """, [shift_id])
        
        shift = cursor.fetchone()
        if not shift:
            return jsonify({'error': 'Shift not found'}), 404
        
        # Get sales by payment method for this shift
        cursor.execute("""
            SELECT 
                payment_method,
                SUM(final_amount) as total
            FROM daily_sales
            WHERE shift_id = ?
            GROUP BY payment_method
        """, [shift_id])
        
        payment_methods = cursor.fetchall()
        
        # Calculate totals by payment method
        cash_amount = 0
        visa_amount = 0
        ewallet_amount = 0
        
        for pm in payment_methods:
            method = pm[0] if pm[0] else ''
            amount = float(pm[1]) if pm[1] else 0
            
            if 'نقد' in method or 'cash' in method.lower():
                cash_amount += amount
            elif 'فيز' in method or 'visa' in method.lower():
                visa_amount += amount
            elif 'محفظ' in method or 'wallet' in method.lower():
                ewallet_amount += amount
        
        # Get cash boxes breakdown
        cursor.execute("""
            SELECT 
                cb.name,
                SUM(ds.final_amount) as total
            FROM daily_sales ds
            LEFT JOIN cash_boxes cb ON ds.cash_box_id = cb.id
            WHERE ds.shift_id = ? AND ds.cash_box_id IS NOT NULL
            GROUP BY cb.name
        """, [shift_id])
        
        cash_boxes_data = cursor.fetchall()
        cash_boxes = [{'name': row[0], 'amount': float(row[1]) if row[1] else 0} for row in cash_boxes_data]
        
        return jsonify({
            'total_sales': float(shift[4]) if shift[4] else 0,
            'total_expenses': float(shift[6]) if shift[6] else 0,
            'total_returns': float(shift[7]) if shift[7] else 0,
            'total_invoices': float(shift[5]) if shift[5] else 0,
            'cash_amount': cash_amount,
            'visa_amount': visa_amount,
            'ewallet_amount': ewallet_amount,
            'cash_boxes': cash_boxes
        })
        
    except Exception as e:
        print(f"Error getting shift summary: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@shift_bp.route('/get_shift_sales_shifts/<int:shift_id>')
@login_required
def get_shift_sales_shifts(shift_id):
    """Get sales for a specific shift (used by shifts.js)."""
    try:
        from database.db import get_db
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id,
                sale_number,
                created_at,
                final_amount,
                payment_method
            FROM daily_sales
            WHERE shift_id = ?
            ORDER BY created_at DESC
        """, [shift_id])
        
        sales_data = cursor.fetchall()
        
        sales = [{
            'id': row[0],
            'sale_number': row[1],
            'created_at': row[2].isoformat() if row[2] else '',
            'final_amount': float(row[3]) if row[3] else 0,
            'payment_method': row[4] or ''
        } for row in sales_data]
        
        return jsonify({'sales': sales})
        
    except Exception as e:
        print(f"Error getting shift sales: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@shift_bp.route('/get_shift_expenses_shifts/<int:shift_id>')
@login_required
def get_shift_expenses_shifts(shift_id):
    """Get expenses for a specific shift (used by shifts.js)."""
    try:
        from database.db import get_db
        conn = get_db()
        cursor = conn.cursor()
        
        # TODO: Add expenses table query when implemented
        # For now, return empty array
        return jsonify({'expenses': []})
        
    except Exception as e:
        print(f"Error getting shift expenses: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@shift_bp.route('/get_shift_returns_shifts/<int:shift_id>')
@login_required
def get_shift_returns_shifts(shift_id):
    """Get returns for a specific shift (used by shifts.js)."""
    try:
        from database.db import get_db
        conn = get_db()
        cursor = conn.cursor()
        
        # TODO: Add returns query when implemented
        # For now, return empty array
        return jsonify({'returns': []})
        
    except Exception as e:
        print(f"Error getting shift returns: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@shift_bp.route('/get_shift_invoices_shifts/<int:shift_id>')
@login_required
def get_shift_invoices_shifts(shift_id):
    """Get invoices for a specific shift (used by shifts.js)."""
    try:
        from database.db import get_db
        conn = get_db()
        cursor = conn.cursor()
        
        # TODO: Add invoices query when implemented
        # For now, return empty array
        return jsonify({'invoices': []})
        
    except Exception as e:
        print(f"Error getting shift invoices: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
