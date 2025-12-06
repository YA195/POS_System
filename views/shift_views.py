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
    return render_template('shifts.html')


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
        
        shift_id = ShiftController.start_shift(user_id, opening_balance)
        
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
