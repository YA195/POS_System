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
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password, permissions FROM users")
        users_data = cursor.fetchall()
        
        users = [{
            'id': row[0],
            'username': row[1],
            'password': row[2],
            'permissions': row[3]
        } for row in users_data]
        
        return jsonify(users)
    except Exception as e:
        print(f"Error getting users: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@settings_bp.route('/get_user/<int:user_id>')
@login_required
@permission_required('settings')
def get_user(user_id):
    """Get a single user by ID."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password, permissions FROM users WHERE id = ?", [user_id])
        user_data = cursor.fetchone()
        
        if user_data:
            user = {
                'id': user_data[0],
                'username': user_data[1],
                'password': user_data[2],
                'permissions': user_data[3] or ''
            }
            return jsonify(user)
        else:
            return jsonify({'success': False, 'error': 'User not found'}), 404
    except Exception as e:
        print(f"Error getting user: {e}")
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
        
        # SQL Server uses TOP instead of LIMIT
        cursor.execute("""
            SELECT TOP 1000 
                id, user_id, username, action_type, table_name, 
                record_id, description, ip_address, created_at
            FROM activity_logs 
            ORDER BY created_at DESC
        """)
        
        logs_data = cursor.fetchall()
        
        # Convert Row objects to lists for JSON serialization
        logs = []
        for log in logs_data:
            logs.append({
                'id': log[0],
                'user_id': log[1],
                'username': log[2] or 'Unknown',
                'action_type': log[3] or '',
                'table_name': log[4] or '',
                'record_id': log[5],
                'description': log[6] or '',
                'ip_address': log[7] or '',
                'created_at': log[8].isoformat() if log[8] else ''
            })
        
        print(f"Loaded {len(logs)} activity logs")
        return jsonify({'success': True, 'logs': logs})
        
    except Exception as e:
        print(f"Error loading activity logs: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@settings_bp.route('/get_activity_stats')
@login_required
def get_activity_stats():
    """Get activity statistics."""
    try:
        from datetime import datetime, timedelta
        conn = get_db()
        cursor = conn.cursor()
        
        # Total logs count
        cursor.execute("SELECT COUNT(*) FROM activity_logs")
        total_logs = cursor.fetchone()[0]
        
        # Today's logs count
        today = datetime.now().date()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM activity_logs 
            WHERE CAST(created_at AS DATE) = ?
        """, [today])
        today_logs = cursor.fetchone()[0]
        
        # Active users (users who performed actions today)
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) 
            FROM activity_logs 
            WHERE CAST(created_at AS DATE) = ?
        """, [today])
        active_users = cursor.fetchone()[0]
        
        return jsonify({
            'success': True,
            'total_logs': total_logs or 0,
            'today_logs': today_logs or 0,
            'active_users': active_users or 0
        })
        
    except Exception as e:
        print(f"Error loading activity stats: {e}")
        import traceback
        traceback.print_exc()
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
