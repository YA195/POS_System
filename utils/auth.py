"""Authentication utilities and decorators."""
from functools import wraps
from flask import session, redirect, url_for, request, render_template
from database.db import get_db


def login_required(f):
    """Decorator to require user login for accessing routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"Checking login for route: {request.path}")  # Debug log
        print(f"Current session: {dict(session)}")  # Debug log
        
        if 'user_id' not in session:
            print("No user_id in session, redirecting to login")
            return redirect(url_for('auth.login'))
            
        # Add session validation
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, permissions 
                FROM users 
                WHERE id = ?
            """, [session['user_id']])
            user = cursor.fetchone()
            
            if not user:
                print(f"User {session['user_id']} not found in database")
                session.clear()
                return redirect(url_for('auth.login'))
                
            # Refresh permissions in session
            session['permissions'] = user[2].split(',') if user[2] else []
            print(f"User permissions refreshed: {session['permissions']}")
                
        except Exception as e:
            print(f"Session validation error: {e}")
            session.clear()
            return redirect(url_for('auth.login'))
            
        return f(*args, **kwargs)
    return decorated_function


def permission_required(permission):
    """Decorator to require specific permission for accessing routes."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                print(f"No user_id in session for permission check: {permission}")  # Debug log
                return redirect(url_for('auth.login'))
            
            if 'permissions' not in session:
                print(f"No permissions in session for user: {session.get('user_id')}")  # Debug log
                return redirect(url_for('auth.login'))
            
            if permission not in session['permissions']:
                print(f"Permission denied: {permission} for user: {session.get('username')}")  # Debug log
                return render_template('403.html'), 403
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def check_session():
    """Check and validate user session before each request."""
    print(f"Session data before checking: {dict(session)}")  # Debug log

    if request.endpoint not in ['auth.login', 'static', 'main.init_db_route']:
        if 'user_id' not in session:
            print(f"Session check: No user_id for endpoint {request.endpoint}")  # Debug log
            return redirect(url_for('auth.login'))

        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE id = ?", [session['user_id']])
            if not cursor.fetchone():
                print(f"Session check: Invalid user_id {session.get('user_id')}")  # Debug log
                session.clear()
                return redirect(url_for('auth.login'))

        except Exception as e:
            print(f"Session check error: {e}")  # Debug log
            session.clear()
            return redirect(url_for('auth.login'))
