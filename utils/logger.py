"""Activity logging utilities."""
from flask import session, request
from database.db import get_db


def log_activity(action_type, description, table_name=None, record_id=None):
    """Log user activity to the activity_logs table"""
    try:
        user_id = session.get('user_id')
        username = session.get('username')
        ip_address = request.remote_addr
        
        if not user_id:
            return  # Don't log if no user is logged in
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO activity_logs (user_id, username, action_type, table_name, record_id, description, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [user_id, username, action_type, table_name, record_id, description, ip_address])
        conn.commit()
    except Exception as e:
        print(f"Failed to log activity: {str(e)}")
        # Don't raise exception - logging failure shouldn't break the main operation
