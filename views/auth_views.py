"""Authentication views."""
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from models.user import User
from utils.logger import log_activity

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if request.method == 'GET':
        return render_template('login.html')
    
    try:
        # Get data from JSON body
        data = request.get_json()
        username = data.get('username') if data else None
        password = data.get('password') if data else None
        
        print(f"Login attempt - Username: {username}, Password provided: {bool(password)}")
        
        if not username or not password:
            print("Missing username or password")
            return jsonify({'success': False, 'message': 'اسم المستخدم وكلمة المرور مطلوبة'}), 400
        
        # Authenticate user
        print("Attempting to authenticate user...")
        user = User.authenticate(username, password)
        print(f"Authentication result: {user}")
        
        if user:
            session.permanent = True
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['permissions'] = user[2].split(',') if user[2] else []
            
            # Log activity
            log_activity('LOGIN', f'User {username} logged in')
            
            return jsonify({
                'success': True,
                'message': 'تم تسجيل الدخول بنجاح',
                'redirect': url_for('main.home')
            })
        else:
            print("Invalid credentials")
            return jsonify({
                'success': False,
                'message': 'اسم المستخدم أو كلمة المرور غير صحيحة'
            }), 401
            
    except Exception as e:
        print(f"Login error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@auth_bp.route('/logout')
def logout():
    """Handle user logout."""
    username = session.get('username', 'Unknown')
    
    # Log activity before clearing session
    log_activity('LOGOUT', f'User {username} logged out')
    
    session.clear()
    return redirect(url_for('auth.login'))
