"""Settings and configuration views."""
from flask import Blueprint, render_template, request, jsonify
from database.db import get_db
from models.user import User
from models.employee import Employee
from utils.auth import login_required, permission_required
from utils.logger import log_activity

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings')
@login_required
@permission_required('settings')
def settings():
    """Render settings page."""
    return render_template('settings.html')


@settings_bp.route('/employees')
@login_required
@permission_required('employees')
def employees():
    """Render employees page."""
    return render_template('employees.html')


@settings_bp.route('/activity_logs')
@login_required
@permission_required('activity_logs')
def activity_logs():
    """Render activity logs page."""
    return render_template('activity_logs.html')


@settings_bp.route('/get_settings')
@login_required
def get_settings():
    """Get application settings."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM settings WHERE id = 1")
        settings = cursor.fetchone()
        
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@settings_bp.route('/save_settings', methods=['POST'])
@login_required
@permission_required('settings')
def save_settings():
    """Save application settings."""
    try:
        data = request.get_json()
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE settings 
            SET printer_name = ?, store_name = ?, store_phone = ?, 
                store_address = ?, receipt_footer = ?
            WHERE id = 1
        """, [
            data.get('printer_name', ''),
            data.get('store_name', ''),
            data.get('store_phone', ''),
            data.get('store_address', ''),
            data.get('receipt_footer', '')
        ])
        conn.commit()
        
        log_activity('UPDATE', 'Updated application settings', 'settings', 1)
        
        return jsonify({'success': True, 'message': 'Settings saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@settings_bp.route('/get_users')
@login_required
@permission_required('settings')
def get_users():
    """Get all users."""
    try:
        users = User.get_all()
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@settings_bp.route('/add_user', methods=['POST'])
@login_required
@permission_required('settings')
def add_user():
    """Add a new user."""
    try:
        data = request.get_json()
        user_id = User.create(data)
        
        log_activity('CREATE', f"Created user: {data['username']}", 'users', user_id)
        
        return jsonify({'success': True, 'user_id': user_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@settings_bp.route('/update_user/<int:user_id>', methods=['PUT'])
@login_required
@permission_required('settings')
def update_user(user_id):
    """Update a user."""
    try:
        data = request.get_json()
        User.update(user_id, data)
        
        log_activity('UPDATE', f"Updated user ID: {user_id}", 'users', user_id)
        
        return jsonify({'success': True, 'message': 'User updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@settings_bp.route('/delete_user/<int:user_id>', methods=['DELETE'])
@login_required
@permission_required('settings')
def delete_user(user_id):
    """Delete a user."""
    try:
        User.delete(user_id)
        
        log_activity('DELETE', f"Deleted user ID: {user_id}", 'users', user_id)
        
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@settings_bp.route('/get_employees')
@login_required
def get_employees():
    """Get all employees."""
    try:
        employees = Employee.get_all()
        return jsonify({'success': True, 'employees': employees})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@settings_bp.route('/add_employee', methods=['POST'])
@login_required
@permission_required('employees')
def add_employee():
    """Add a new employee."""
    try:
        data = request.get_json()
        employee_id = Employee.create(data)
        
        log_activity('CREATE', f"Created employee: {data['name']}", 'employees', employee_id)
        
        return jsonify({'success': True, 'employee_id': employee_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@settings_bp.route('/get_activity_logs')
@login_required
def get_activity_logs():
    """Get activity logs."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM activity_logs 
            ORDER BY created_at DESC 
            LIMIT 1000
        """)
        logs = cursor.fetchall()
        
        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@settings_bp.route('/get_printers')
@login_required
def get_printers():
    """Get available printers."""
    try:
        from utils.printer import get_available_printers
        printers = get_available_printers()
        return jsonify({'success': True, 'printers': printers})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
