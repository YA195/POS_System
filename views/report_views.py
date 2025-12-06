"""Report views."""
from flask import Blueprint, render_template, request, jsonify
from controllers.report_controller import ReportController
from utils.auth import login_required, permission_required

report_bp = Blueprint('reports', __name__)


@report_bp.route('/reports')
@login_required
@permission_required('reports')
def reports():
    """Render reports page."""
    return render_template('reports.html')


@report_bp.route('/reports_shifts')
@login_required
@permission_required('reports')
def reports_shifts():
    """Render shift reports page."""
    return render_template('reports_shifts.html')


@report_bp.route('/item_movement')
@login_required
@permission_required('reports')
def item_movement():
    """Render item movement report page."""
    return render_template('item_movement.html')


@report_bp.route('/api/sales_report')
@login_required
def sales_report():
    """Get sales report data."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        report_data = ReportController.get_sales_report(start_date, end_date)
        
        return jsonify({
            'success': True,
            'data': report_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@report_bp.route('/api/inventory_report')
@login_required
def inventory_report():
    """Get inventory report data."""
    try:
        report_data = ReportController.get_inventory_report()
        
        return jsonify({
            'success': True,
            'data': report_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@report_bp.route('/api/low_stock_report')
@login_required
def low_stock_report():
    """Get low stock items."""
    try:
        threshold = request.args.get('threshold', 10, type=int)
        items = ReportController.get_low_stock_items(threshold)
        
        return jsonify({
            'success': True,
            'items': items
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@report_bp.route('/api/profit_summary')
@login_required
def profit_summary():
    """Get profit summary."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        profit = ReportController.get_profit_report(start_date, end_date)
        
        return jsonify({
            'success': True,
            'profit': profit
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@report_bp.route('/api/item_movement_data')
@login_required
def item_movement_data():
    """Get item movement data."""
    try:
        item_id = request.args.get('item_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        movements = ReportController.get_item_movement_report(item_id, start_date, end_date)
        
        return jsonify({
            'success': True,
            'movements': movements
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@report_bp.route('/api/reports_shifts_data')
@login_required
def reports_shifts_data():
    """Get shift report data."""
    try:
        # Implementation for shift reports
        # This would aggregate data from multiple shifts
        
        return jsonify({
            'success': True,
            'message': 'Shift reports data endpoint'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
