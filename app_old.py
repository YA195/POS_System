import sys
import os
import subprocess
from flask import g,Flask, render_template, jsonify, request, session, redirect, url_for, send_from_directory
from database.db import (
    get_db, 
    init_app, 
    begin_transaction,  # Add these imports
    commit_transaction, 
    rollback_transaction
)
import win32print
import pyodbc
import random
import win32ui
from win32con import *
from datetime import datetime, timedelta  
import re
from database.db import init_app
from functools import wraps
import glob
try:
    import barcode
    from barcode.writer import ImageWriter
    from PIL import Image, ImageDraw, ImageFont, ImageWin
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False
    print("Warning: python-barcode and/or PIL not available. Barcode printing will use text only.")


# ========== HARDWARE LOCK CHECK ==========
def check_hardware_lock():
    """Check if the application is running on authorized hardware"""
    # 1. Your Target UUID
    AUTHORIZED_UUID =  "4C4C4544-0059-3510-8037-B2C04F4A5033" 
    
    try:
        # 2. Get the Raw Output
        # (We use .decode() to ensure we have a string, not bytes)
        result = subprocess.check_output(
            'wmic csproduct get uuid', 
            shell=True
        ).decode()
        
        # 3. THE FIX: Aggressive Cleaning
        # Remove the word "UUID" if it's there
        machine_uuid = result.replace("UUID", "")
        # Remove ALL whitespace (newlines \n, returns \r, spaces, tabs)
        machine_uuid = "".join(machine_uuid.split())
        
        # 4. Compare
        if machine_uuid != AUTHORIZED_UUID:
            print("!!! HARDWARE MISMATCH !!!")
            print(f"Found:    [{machine_uuid}]")
            sys.exit(1)
            
    except Exception as e:
        print(f"Hardware check error: {e}")
        sys.exit(1)

# Call this immediately at the start of app.py
check_hardware_lock()


# ========== PATH DETECTION FOR NUITKA ==========
def get_base_path():
    """Get the base path for the application (works for both script and frozen exe)"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for Nuitka compiled"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - resources are embedded
        base_path = os.path.dirname(sys.argv[0])
        return os.path.join(base_path, relative_path)
    else:
        # Running as script
        base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

# Set up paths
BASE_PATH = get_base_path()
TEMPLATE_FOLDER = get_resource_path('templates')
STATIC_FOLDER = get_resource_path('static')
CONFIG_PATH = r'C:\Program Files\ELmohandes\config.txt'  # Config in Program Files

# Initialize Flask app with correct paths
app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)
init_app(app)
# Track the last printed/created daily sale id (used by print-last endpoints)
last_sale_id = None

# Helper function to log user activities
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
# Development only - change in production!
app.secret_key = 'dev_secret_key_123456789'
app.permanent_session_lifetime = timedelta(hours=12)  # Session timeout
app.config['SESSION_TYPE'] = 'flask_session'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)

#region Database Initialization

# Add cache control
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# Serve static files efficiently
@app.route('/static/<path:filename>')
def serve_static(filename):
    cache_timeout = 31536000  # 1 year in seconds
    return send_from_directory(STATIC_FOLDER, filename, max_age=cache_timeout)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"Checking login for route: {request.path}")  # Debug log
        print(f"Current session: {dict(session)}")  # Debug log
        
        if 'user_id' not in session:
            print("No user_id in session, redirecting to login")
            return redirect(url_for('login'))
            
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
                return redirect(url_for('login'))
                
            # Refresh permissions in session
            session['permissions'] = user[2].split(',') if user[2] else []
            print(f"User permissions refreshed: {session['permissions']}")
                
        except Exception as e:
            print(f"Session validation error: {e}")
            session.clear()
            return redirect(url_for('login'))
            
        return f(*args, **kwargs)
    return decorated_function
def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                print(f"No user_id in session for permission check: {permission}")  # Debug log
                return redirect(url_for('login'))
            
            if 'permissions' not in session:
                print(f"No permissions in session for user: {session.get('user_id')}")  # Debug log
                return redirect(url_for('login'))
            
            if permission not in session['permissions']:
                print(f"Permission denied: {permission} for user: {session.get('username')}")  # Debug log
                return render_template('403.html'), 403
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.before_request
def check_session():
    print(f"Session data before checking: {dict(session)}")  # Debug log

    if request.endpoint not in ['login', 'static', 'init_db_route']:
        if 'user_id' not in session:
            print(f"Session check: No user_id for endpoint {request.endpoint}")  # Debug log
            return redirect(url_for('login'))

        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE id = ?", [session['user_id']])
            if not cursor.fetchone():
                print(f"Session check: Invalid user_id {session.get('user_id')}")  # Debug log
                session.clear()
                return redirect(url_for('login'))

        except Exception as e:
            print(f"Session check error: {e}")  # Debug log
            session.clear()
            return redirect(url_for('login'))

@app.route('/vendor/<path:filename>')
def vendor_files(filename):
    return send_from_directory('static/vendor', filename)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
        
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        print(f"Login attempt for user: {username}")  # Debug log
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Modified query to ensure permissions are properly fetched
        cursor.execute("""
            SELECT id, username, permissions 
            FROM users 
            WHERE username = ? AND password = ?
        """, [username, password])
        
        user = cursor.fetchone()
        if user:
            # Make session permanent
            session.permanent = True
            
            # Parse permissions properly
            permissions = user[2].split(',') if user[2] else []
            
            # Set session data
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['permissions'] = permissions
            session.modified = True  # Ensure session changes are saved

            # Debug log
            print(f"Login successful for user: {username}")
            print(f"User permissions: {permissions}")
            print(f"Session data: {dict(session)}")
            
            # Log the login activity
            log_activity('login', f'User logged in: {username}', 'users', user[0])
            
            return jsonify({'success': True, 'redirect_url': url_for('Home')})
        
        print(f"Login failed for user: {username}")  # Debug log
        return jsonify({
            'success': False, 
            'error': 'Invalid credentials'
        })
        
    except Exception as e:
        print(f"Login error: {e}")  # Debug log
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    username = session.get('username')
    
    print(f"Logging out user: {username}")  # Debug log
    
    # Log the logout activity
    if user_id:
        log_activity('logout', f'User logged out: {username}', 'users', user_id)
    
    session.clear()
    return redirect(url_for('login'))

#endregion

#region Main Routes
@app.route('/Home')
@login_required
def Home():
    try:
        print(f"Session data at Home: {dict(session)}")  # Debug log
        print(f"Current user permissions: {session.get('permissions', [])}")  # Debug log

        # Check if user has basic permissions
        if not session.get('permissions'):
            print("No permissions found in session")
            return redirect(url_for('login'))

        return render_template('home.html')

    except Exception as e:
        print(f"Error in Home route: {e}")
        return redirect(url_for('login'))


@app.route('/reports')
@login_required
@permission_required('reports')
def reports():
    return render_template('reports.html')

@app.route('/inventory_audit')
@login_required
def inventory_audit():
    return render_template('inventory_audit.html')

#endregion

#region Items Management
@app.route('/items')
@login_required
@permission_required('items')
def items():
    db = get_db()
    cursor = db.cursor()
    
    # Only include active traders
    cursor.execute("SELECT id, name FROM traders WHERE ISNULL(active, 1) = 1")
    traders = cursor.fetchall()
    
    cursor.execute("SELECT id, name FROM categories WHERE ISNULL(active,1) = 1")
    categories_raw = cursor.fetchall()
    
    # Convert categories to list of dicts for JSON serialization
    categories = [{'id': row[0], 'name': row[1]} for row in categories_raw]
    
    cursor.execute("""
        SELECT i.*, c.name as category_name, t.name as trader_name 
        FROM items i 
        LEFT JOIN categories c ON i.category_id = c.id 
        LEFT JOIN traders t ON i.trader_id = t.id
        WHERE ISNULL(i.active,1) = 1
    """)
    items = cursor.fetchall()
    
    db.close()
    return render_template('items.html', traders=traders, categories=categories, items=items)

@app.route('/get_items')
@login_required
@permission_required('items')
def get_items():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT i.*, c.name as category_name, t.name as trader_name 
        FROM items i 
        LEFT JOIN categories c ON i.category_id = c.id 
        LEFT JOIN traders t ON i.trader_id = t.id
        WHERE ISNULL(i.active,1) = 1
    """)
    items = [dict(zip([column[0] for column in cursor.description], row)) 
             for row in cursor.fetchall()]
    db.close()
    return jsonify(items)

@app.route('/get_item/<barcode>')
def get_item(barcode):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT * FROM items
        WHERE (barcode = ? OR '(,,)' + ISNULL(barcode2,'') + '(,,)' LIKE '%(,,)' + ? + '(,,)%')
          AND ISNULL(active,1) = 1
    """, [barcode, barcode])
    item = cursor.fetchone()
    db.close()
    
    if item:
        return jsonify({
            'id': item.id,
            'name': item.name,
            'category_id': item.category_id,
            'buy_price': item.buy_price,
            'sell_price': item.sell_price,
            'quantity': item.quantity,
            'trader_id': item.trader_id,
            'barcode': getattr(item, 'barcode', None),
            'barcode2': getattr(item, 'barcode2', None)
        })
    return jsonify({}), 404

@app.route('/save_item', methods=['POST'])
def save_item():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    barcode = data.get('barcode', '').strip()
    barcode2 = data.get('barcode2', '').strip()
    
    # Check if main barcode exists in any item
    if barcode:
        cursor.execute("""
            SELECT id, name FROM items 
            WHERE (barcode = ? OR '(,,)' + ISNULL(barcode2,'') + '(,,)' LIKE '%(,,)' + ? + '(,,)%')
            AND ISNULL(active,1) = 1
        """, (barcode, barcode))
        existing_item = cursor.fetchone()
        
        if existing_item:
            return jsonify({
                'success': False, 
                'message': f'الباركود {barcode} موجود بالفعل في المنتج: {existing_item[1]}'
            })
    
    # Check if any barcode in barcode2 exists in any item
    if barcode2:
        barcode2_list = [b.strip() for b in barcode2.split('(,,)') if b.strip()]
        for bc in barcode2_list:
            cursor.execute("""
                SELECT id, name FROM items 
                WHERE (barcode = ? OR '(,,)' + ISNULL(barcode2,'') + '(,,)' LIKE '%(,,)' + ? + '(,,)%')
                AND ISNULL(active,1) = 1
            """, (bc, bc))
            existing_item = cursor.fetchone()
            
            if existing_item:
                return jsonify({
                    'success': False, 
                    'message': f'الباركود {bc} موجود بالفعل في المنتج: {existing_item[1]}'
                })
    
    # Get current user
    user_id = session.get('user_id')
    
    try:
        cursor.execute("""
            INSERT INTO items (barcode, barcode2, name, category_id, buy_price, sell_price, quantity, trader_id, created_by)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (barcode, barcode2, data['name'], data['category_id'], 
              data['buy_price'], data['sell_price'], data['quantity'], 
              data['trader_id'], user_id))
        
        new_item = cursor.fetchone()
        new_item_id = new_item[0] if new_item else None
        
        # Log the activity
        if new_item_id:
            log_activity('create', f'Item created: {data["name"]} (Barcode: {barcode})', 'items', new_item_id)
        
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_item/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    barcode = data.get('barcode', '').strip()
    barcode2 = data.get('barcode2', '').strip()
    
    # Get current item's barcodes to check if they changed
    cursor.execute("""
        SELECT barcode, barcode2 
        FROM items 
        WHERE id = ?
    """, (item_id,))
    current_item = cursor.fetchone()
    
    if not current_item:
        return jsonify({'success': False, 'message': 'المنتج غير موجود'})
    
    current_barcode = current_item[0] or ''
    current_barcode2 = current_item[1] or ''
    
    # Check if main barcode exists in any OTHER item (only if barcode changed)
    if barcode and barcode != current_barcode:
        cursor.execute("""
            SELECT id, name FROM items 
            WHERE (barcode = ? OR '(,,)' + ISNULL(barcode2,'') + '(,,)' LIKE '%(,,)' + ? + '(,,)%')
            AND id != ?
            AND ISNULL(active,1) = 1
        """, (barcode, barcode, item_id))
        existing_item = cursor.fetchone()
        
        if existing_item:
            return jsonify({
                'success': False, 
                'message': f'الباركود {barcode} موجود بالفعل في المنتج: {existing_item[1]}'
            })
    
    # Check if any barcode in barcode2 exists in any OTHER item (only if barcode2 changed)
    if barcode2 and barcode2 != current_barcode2:
        barcode2_list = [b.strip() for b in barcode2.split('(,,)') if b.strip()]
        for bc in barcode2_list:
            cursor.execute("""
                SELECT id, name FROM items 
                WHERE (barcode = ? OR '(,,)' + ISNULL(barcode2,'') + '(,,)' LIKE '%(,,)' + ? + '(,,)%')
                AND id != ?
                AND ISNULL(active,1) = 1
            """, (bc, bc, item_id))
            existing_item = cursor.fetchone()
            
            if existing_item:
                return jsonify({
                    'success': False, 
                    'message': f'الباركود {bc} موجود بالفعل في المنتج: {existing_item[1]}'
                })
    
    # Get current user
    user_id = session.get('user_id')
    
    try:
        # Get current prices before updating
        cursor.execute("""
            SELECT buy_price, sell_price 
            FROM items 
            WHERE id = ?
        """, (item_id,))
        old_prices = cursor.fetchone()
        
        if old_prices:
            old_buy_price = float(old_prices[0])
            old_sell_price = float(old_prices[1])
            new_buy_price = float(data['buy_price'])
            new_sell_price = float(data['sell_price'])
            
            # Check if prices have changed
            price_changed = (old_buy_price != new_buy_price or old_sell_price != new_sell_price)
        else:
            price_changed = False
        
        # Update the item
        cursor.execute("""
            UPDATE items 
            SET barcode=?, barcode2=?, name=?, category_id=?, buy_price=?, 
                sell_price=?, quantity=?, trader_id=?, updated_by=?
            WHERE id=?
        """, (barcode, barcode2, data['name'], data['category_id'], 
              data['buy_price'], data['sell_price'], data['quantity'], 
              data['trader_id'], user_id, item_id))
        
        # If prices changed, record in item_price_history
        if price_changed:
            cursor.execute("""
                INSERT INTO item_price_history (item_id, old_buy_price, new_buy_price, old_sell_price, new_sell_price, change_date)
                VALUES (?, ?, ?, ?, ?, GETDATE())
            """, (item_id, old_buy_price, new_buy_price, old_sell_price, new_sell_price))
        
        db.commit()
        
        # Log the activity
        if price_changed:
            log_activity('price_update', f'Item #{item_id} prices updated: {data["name"]} - Buy: {old_buy_price}→{new_buy_price}, Sell: {old_sell_price}→{new_sell_price}', 'items', item_id)
        else:
            log_activity('update', f'Item #{item_id} updated: {data["name"]}', 'items', item_id)
        
        return jsonify({'success': True, 'price_changed': price_changed})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/delete_item/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    db = get_db()
    cursor = db.cursor()
    try:
        # Get item name before deletion
        cursor.execute("SELECT name FROM items WHERE id = ?", (item_id,))
        item_result = cursor.fetchone()
        item_name = item_result[0] if item_result else f"Item #{item_id}"
        
        # Soft-delete
        cursor.execute("UPDATE items SET active = 0 WHERE id = ?", (item_id,))
        db.commit()
        
        # Log the activity
        log_activity('delete', f'Item deleted: {item_name}', 'items', item_id)
        
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})
# new endpoint: update barcode2 values from modal
@app.route('/update_barcodes/<int:item_id>', methods=['POST'])
@login_required
@permission_required('items')
def update_barcodes(item_id):
    """Accept JSON payload to update barcode2 for an item.
       Supported payloads:
         { "barcodes": ["b1","b2"] }
         { "barcodes": "b1(,,)b2" }
       The server normalizes and stores values joined with '(,,)'.
    """
    payload = request.get_json(silent=True) or {}
    raw = payload.get('barcodes')

    if raw is None:
        return jsonify({'success': False, 'message': 'No barcodes provided'}), 400

    # Normalize into list of trimmed non-empty strings
    parts = []
    if isinstance(raw, str):
        # If already joined with (,,), split on that; otherwise try splitting on commas/newlines
        if '(,,)' in raw:
            parts = [p.strip() for p in raw.split('(,,)') if p.strip()]
        else:
            parts = [p.strip() for p in re.split('[,\r\n]+', raw) if p.strip()]
    elif isinstance(raw, list):
        parts = [str(p).strip() for p in raw if str(p).strip()]
    else:
        return jsonify({'success': False, 'message': 'Invalid barcodes format'}), 400

    # Join with '(,,)' to match existing DB usage
    joined = '(,,)'.join(parts) if parts else ''

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE items SET barcode2 = ? WHERE id = ?", (joined, item_id))
        db.commit()
        return jsonify({'success': True, 'barcode2': joined})
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/get_next_barcode')
@login_required
@permission_required('items')
def get_next_barcode():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT ISNULL(MAX(TRY_CAST(barcode AS INT)), 0) + 1 FROM items WHERE TRY_CAST(barcode AS INT) IS NOT NULL")
    next_barcode = cursor.fetchone()[0]
    db.close()
    return jsonify({'next_barcode': next_barcode})

@app.route('/get_item_price_history/<int:item_id>')
@login_required
@permission_required('items')
def get_item_price_history(item_id):
    """Get price change history for an item"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT 
            id,
            old_buy_price,
            new_buy_price,
            old_sell_price,
            new_sell_price,
            change_date,
            invoice_id
        FROM item_price_history
        WHERE item_id = ?
        ORDER BY change_date DESC
    """, (item_id,))
    
    history = []
    for row in cursor.fetchall():
        history.append({
            'id': row[0],
            'old_buy_price': float(row[1]),
            'new_buy_price': float(row[2]),
            'old_sell_price': float(row[3]),
            'new_sell_price': float(row[4]),
            'change_date': row[5].strftime('%Y-%m-%d %H:%M:%S') if row[5] else None,
            'invoice_id': row[6]
        })
    
    db.close()
    return jsonify(history)

@app.route('/check_barcode_exists/<barcode>')
@login_required
@permission_required('items')
def check_barcode_exists(barcode):
    """Check if a barcode already exists in either barcode or barcode2 columns"""
    if not barcode or not barcode.strip():
        return jsonify({'exists': False, 'item_name': None})
    
    db = get_db()
    cursor = db.cursor()
    
    # Check if barcode exists in either barcode column or within barcode2 (separated by (,,))
    cursor.execute("""
        SELECT id, name FROM items 
        WHERE (barcode = ? OR '(,,)' + ISNULL(barcode2,'') + '(,,)' LIKE '%(,,)' + ? + '(,,)%')
        AND ISNULL(active,1) = 1
    """, [barcode, barcode])
    
    item = cursor.fetchone()
    db.close()
    
    if item:
        return jsonify({
            'exists': True, 
            'item_id': item[0],
            'item_name': item[1]
        })
    else:
        return jsonify({'exists': False, 'item_name': None})

#endregion

#region Traders Management
@app.route('/traders')
@login_required
@permission_required('items')  # Since traders are related to items
def traders():
    db = get_db()
    cursor = db.cursor()
    
    # Get traders with company names
    cursor.execute("""
        SELECT t.id, t.name, t.phone, t.days, t.company, c.name as company_name
        FROM traders t
        LEFT JOIN companies c ON t.company = c.id
        WHERE ISNULL(t.active, 1) = 1
    """)
    traders_data = cursor.fetchall()
    
    traders = []
    for row in traders_data:
        trader = {
            'id': row[0],
            'name': row[1], 
            'phone': row[2],
            'days': row[3],
            'company': row[4],
            'company_name': row[5]
        }
        traders.append(trader)
    
    # Get companies for dropdown
    cursor.execute("SELECT id, name FROM companies")
    companies = cursor.fetchall()
    
    db.close()
    return render_template('traders.html', traders=traders, companies=companies)



@app.route('/get_traders')
@login_required
@permission_required('items')
def get_traders():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT t.id, t.name, t.phone, t.days, t.company, c.name as company_name
        FROM traders t
        LEFT JOIN companies c ON t.company = c.id
        WHERE ISNULL(t.active, 1) = 1
    """)
    traders = cursor.fetchall()
    
    traders_list = [{
        'id': trader[0],
        'name': trader[1],
        'phone': trader[2],
        'days': trader[3],
        'company': trader[4],
        'company_name': trader[5]
    } for trader in traders]
    
    return jsonify(traders_list)
@app.route('/save_trader', methods=['POST'])
def save_trader():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    # Get current user
    user_id = session.get('user_id')
    
    try:
        print(f"save_trader called with: {data}")
        cursor.execute("""
            INSERT INTO traders (name, phone, days, company, active, created_by) 
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, 1, ?)
        """, (data['name'], data['phone'], data['days'], data['company'], user_id))
        
        trader_result = cursor.fetchone()
        trader_id = trader_result[0] if trader_result else None
        
        db.commit()
        
        # Log the activity
        if trader_id:
            log_activity('create', f'Trader created: {data["name"]}', 'traders', trader_id)
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in save_trader: {e}")
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_trader/<int:trader_id>', methods=['PUT'])
def update_trader(trader_id):
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    # Get current user
    user_id = session.get('user_id')
    
    try:
        print(f"update_trader {trader_id} called with: {data}")
        cursor.execute("""
            UPDATE traders 
            SET name=?, phone=?, days=?, company=?, updated_by=? 
            WHERE id=?
        """, (data['name'], data['phone'], data['days'], data['company'], user_id, trader_id))
        db.commit()
        
        # Log the activity
        log_activity('update', f'Trader #{trader_id} updated: {data["name"]}', 'traders', trader_id)
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in update_trader: {e}")
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/delete_trader/<int:trader_id>', methods=['DELETE'])
def delete_trader(trader_id):
    db = get_db()
    cursor = db.cursor()
    
    try:
        print(f"delete_trader called for id: {trader_id}")
        
        # Get trader name before deletion
        cursor.execute("SELECT name FROM traders WHERE id = ?", (trader_id,))
        trader_result = cursor.fetchone()
        trader_name = trader_result[0] if trader_result else f"Trader #{trader_id}"
        
        # Soft-delete: mark as inactive instead of deleting to avoid FK conflicts
        cursor.execute("UPDATE traders SET active = 0 WHERE id = ?", (trader_id,))
        db.commit()
        
        # Log the activity
        log_activity('delete', f'Trader deleted: {trader_name}', 'traders', trader_id)
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in delete_trader: {e}")
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})
#endregion

#region Categories Management
@app.route('/categories')
@login_required
@permission_required('categories')
def categories():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM categories WHERE ISNULL(active,1) = 1")
    categories_data = cursor.fetchall()
    
    categories = []
    for row in categories_data:
        category = {
            'id': row[0],
            'name': row[1]
        }
        categories.append(category)
    
    db.close()
    return render_template('categories.html', categories=categories)

@app.route('/get_categories')
@login_required
@permission_required('categories')
def get_categories():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT c.id, c.name, c.section_id, s.name as section_name
        FROM categories c
        LEFT JOIN sections s ON c.section_id = s.id
        WHERE ISNULL(c.active,1) = 1
        ORDER BY s.name, c.name
    """)
    categories_data = cursor.fetchall()
    
    categories = [{
        'id': row[0],
        'name': row[1],
        'section_id': row[2],
        'section_name': row[3]
    } for row in categories_data]
    
    db.close()
    return jsonify(categories)

@app.route('/save_category', methods=['POST'])
def save_category():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    # Get current user
    user_id = session.get('user_id')
    
    try:
        cursor.execute("""
            INSERT INTO categories (name, section_id) 
            VALUES (?, ?)
        """, (data['name'], data.get('section_id')))
        
        db.commit()
        category_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
        
        # Log the activity
        log_activity('create', f'Category created: {data["name"]}', 'categories', category_id)
        
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_category/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    # Get current user
    user_id = session.get('user_id')
    
    try:
        cursor.execute("""
            UPDATE categories 
            SET name=?, section_id=? 
            WHERE id=?
        """, (data['name'], data.get('section_id'), category_id))
        db.commit()
        
        # Log the activity
        log_activity('update', f'Category #{category_id} updated: {data["name"]}', 'categories', category_id)
        
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/delete_category/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Get category name before deletion
        cursor.execute("SELECT name FROM categories WHERE id=?", (category_id,))
        category_result = cursor.fetchone()
        category_name = category_result[0] if category_result else f"Category #{category_id}"
        
        # Soft-delete
        cursor.execute("UPDATE categories SET active = 0 WHERE id=?", (category_id,))
        db.commit()
        
        # Log the activity
        log_activity('delete', f'Category deleted: {category_name}', 'categories', category_id)
        
        return jsonify({'success': True})
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})           
#endregion

#region Sections Management
@app.route('/get_sections')
@login_required
@permission_required('categories')
def get_sections():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, name FROM sections WHERE ISNULL(active,1) = 1 ORDER BY name")
    sections_data = cursor.fetchall()
    
    sections = [{
        'id': row[0],
        'name': row[1]
    } for row in sections_data]
    
    db.close()
    return jsonify(sections)

@app.route('/save_section', methods=['POST'])
@login_required
@permission_required('categories')
def save_section():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    user_id = session.get('user_id')
    
    try:
        cursor.execute(
            "INSERT INTO sections (name, active) VALUES (?, 1)",
            [data['name']]
        )
        db.commit()
        
        section_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
        log_activity('create', f"Section created: {data['name']}", 'sections', section_id)
        
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_section/<int:section_id>', methods=['PUT'])
@login_required
@permission_required('categories')
def update_section(section_id):
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    user_id = session.get('user_id')
    
    try:
        cursor.execute(
            "UPDATE sections SET name=? WHERE id=?",
            [data['name'], section_id]
        )
        db.commit()
        
        log_activity('update', f"Section updated: {data['name']}", 'sections', section_id)
        
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/delete_section/<int:section_id>', methods=['DELETE'])
@login_required
@permission_required('categories')
def delete_section(section_id):
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Check if section has categories
        cursor.execute("SELECT COUNT(*) FROM categories WHERE section_id = ? AND ISNULL(active,1) = 1", (section_id,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            return jsonify({'success': False, 'message': f'لا يمكن حذف القسم لأنه يحتوي على {count} فئة'})
        
        # Get section name before deletion
        cursor.execute("SELECT name FROM sections WHERE id=?", (section_id,))
        section_result = cursor.fetchone()
        section_name = section_result[0] if section_result else f"Section #{section_id}"
        
        # Soft-delete
        cursor.execute("UPDATE sections SET active = 0 WHERE id=?", (section_id,))
        db.commit()
        
        log_activity('delete', f'Section deleted: {section_name}', 'sections', section_id)
        
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})
#endregion

#region Companies Management
@app.route('/companies')
@login_required
@permission_required('companies')
def companies():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM companies WHERE ISNULL(active,1) = 1")
    companies_data = cursor.fetchall()
    
    companies = [{
        'id': row[0],
        'name': row[1],
        'phone': row[2]
    } for row in companies_data]
    
    db.close()
    return render_template('companies.html', companies=companies)

@app.route('/get_companies')
@login_required
@permission_required('companies')
def get_companies():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM companies WHERE ISNULL(active,1) = 1")
    companies_data = cursor.fetchall()
    
    companies = [{
        'id': row[0],
        'name': row[1],
        'phone': row[2]
    } for row in companies_data]
    
    db.close()
    return jsonify(companies)

@app.route('/save_company', methods=['POST'])
def save_company():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    # Get current user
    user_id = session.get('user_id')
    
    try:
        cursor.execute("""
            INSERT INTO companies (name, phone, created_by) 
            OUTPUT INSERTED.id
            VALUES (?, ?, ?)
        """, (data['name'], data['phone'], user_id))
        
        company_result = cursor.fetchone()
        company_id = company_result[0] if company_result else None
        
        db.commit()
        
        # Log the activity
        if company_id:
            log_activity('create', f'Company created: {data["name"]}', 'companies', company_id)
        
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_company/<int:company_id>', methods=['PUT'])
def update_company(company_id):
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    # Get current user
    user_id = session.get('user_id')
    
    try:
        cursor.execute("""
            UPDATE companies 
            SET name=?, phone=?, updated_by=? 
            WHERE id=?
        """, (data['name'], data['phone'], user_id, company_id))
        db.commit()
        
        # Log the activity
        log_activity('update', f'Company #{company_id} updated: {data["name"]}', 'companies', company_id)
        
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/delete_company/<int:company_id>', methods=['DELETE'])
def delete_company(company_id):
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Get company name before deletion
        cursor.execute("SELECT name FROM companies WHERE id=?", (company_id,))
        company_result = cursor.fetchone()
        company_name = company_result[0] if company_result else f"Company #{company_id}"
        
        # Soft-delete
        cursor.execute("UPDATE companies SET active = 0 WHERE id=?", (company_id,))
        db.commit()
        
        # Log the activity
        log_activity('delete', f'Company deleted: {company_name}', 'companies', company_id)
        
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)})
#endregion

#region ADD invoice

@app.route('/invoice')
@login_required
@permission_required('items')  # Since invoices are related to items
def invoice():
     return render_template('invoice.html', 
                         jquery_ui_css=url_for('static', filename='vendor/jquery-ui.min.css'),
                         jquery_ui_js=url_for('static', filename='vendor/jquery-ui.min.js'))


#endregion

#region Invoice Management

@app.route('/get_item_details/<barcode>')
def get_item_details(barcode):
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Update the query to include category_id and last quantity_type
        cursor.execute("""
            SELECT i.id, i.barcode, i.name, i.buy_price, i.sell_price, i.category_id,
                   COALESCE((
                       SELECT TOP 1 ii.quantity_type 
                       FROM invoice_items ii 
                       JOIN invoices inv ON ii.invoice_id = inv.id 
                       WHERE ii.item_id = i.id 
                       ORDER BY inv.invoice_date DESC
                   ), 1) as last_quantity_type
            FROM items i 
            WHERE i.barcode = ?
        """, [barcode])
        
        item = cursor.fetchone()
        if item:
            return jsonify({
                'id': item[0],
                'barcode': item[1],
                'name': item[2],
                'buy_price': float(item[3]),
                'sell_price': float(item[4]),
                'category_id': item[5],
                'last_quantity_type': item[6]  # Include last quantity type
            })
        return jsonify({}), 404
        
    except Exception as e:
        print(f"Error getting item details: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

            
@app.route('/get_item_suggestions')
def get_item_suggestions():
    search = request.args.get('term', '')
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT i.id, i.barcode, i.name, i.buy_price, i.sell_price, i.category_id,
               COALESCE((
                   SELECT TOP 1 ii.quantity_type 
                   FROM invoice_items ii 
                   JOIN invoices inv ON ii.invoice_id = inv.id 
                   WHERE ii.item_id = i.id 
                   ORDER BY inv.invoice_date DESC
               ), 1) as last_quantity_type
        FROM items i 
        WHERE i.name LIKE ? OR i.barcode LIKE ? OR ISNULL(i.barcode2,'') LIKE ?
    """, (f'%{search}%', f'%{search}%', f'%{search}%'))
    items = cursor.fetchall()
    db.close()
    
    return jsonify([{
        'id': item[0],
        'barcode': item[1], 
        'name': item[2],
        'buy_price': float(item[3]),
        'sell_price': float(item[4]),
        'category_id': item[5],
        'last_quantity_type': item[6]
    } for item in items])

@app.route('/save_invoice', methods=['POST'])
def save_invoice():
    conn = None
    cursor = None
    try:
        data = request.json
        print("Received data:", data)  # Debug log

        # Validate required fields
        required_fields = {
            'trader_id': 'Trader ID',
            'payment_type': 'Payment Type',
            'discount_type': 'Discount Type',
            'total_amount': 'Total Amount',
            'subtotal': 'Subtotal',
            'items': 'Invoice Items'
        }
        
        for field, name in required_fields.items():
            if field not in data or not data[field]:
                print(f"Missing required field: {name}")
                return jsonify({
                    'success': False, 
                    'error': f'Missing required field: {name}'
                }), 400

        conn = get_db()
        cursor = conn.cursor()

        # Get active shift
        cursor.execute("""
            SELECT TOP 1 id FROM shifts 
            WHERE status = 'active' 
            ORDER BY start_time DESC
        """)
        shift = cursor.fetchone()
        if not shift:
            return jsonify({
                'success': False,
                'error': 'No active shift found'
            }), 400
        
        shift_id = shift[0]

        # Get company_id from trader
        cursor.execute("SELECT company FROM traders WHERE id = ? AND ISNULL(active,1) = 1", [data['trader_id']])
        company_result = cursor.fetchone()
        if not company_result:
            print("Invalid trader_id")
            return jsonify({
                'success': False, 
                'error': 'Invalid trader_id'
            }), 400
            
        company_id = company_result[0]

        # Start transaction
        cursor.execute("BEGIN TRANSACTION")

        # Get current user
        user_id = session.get('user_id')
        
        # Insert invoice with shift_id and user_id
        cursor.execute("""
            INSERT INTO invoices (
                total_amount, subtotal, discount_value, discount_type, 
                discount_amount, payment_type, paid_amount, remaining_amount, 
                trader_id, company_id, shift_id, status, payment_status, user_id
            ) OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            float(data['total_amount']),
            float(data['subtotal']),
            float(data.get('discount_value', 0)),
            data['discount_type'],
            float(data.get('discount_amount', 0)),
            data['payment_type'],
            float(data.get('paid_amount', 0)),
            float(data.get('remaining_amount', 0)),
            data['trader_id'],
            company_id,
            shift_id,
            'active',
            'unpaid' if float(data.get('paid_amount', 0)) == 0 else 
            'paid' if float(data.get('paid_amount', 0)) >= float(data['total_amount']) else 'partial',
            user_id
        ))

        invoice_id = cursor.fetchone()[0]

        # Add initial payment to history if paid_amount > 0
        paid_amount = float(data.get('paid_amount', 0))
        discount_amount = float(data.get('discount_amount', 0))
        payment_type = data.get('payment_type')
        
        if paid_amount > 0:
            # Insert the actual payment
            cursor.execute("""
                INSERT INTO invoice_payments (invoice_id, amount, payment_date, notes)
                VALUES (?, ?, GETDATE(), ?)
            """, (invoice_id, paid_amount, f'Payment - {payment_type}'))
            
            # If there was a discount and payment is immediate, insert discount as negative payment
            if discount_amount > 0 and payment_type == 'immediate':
                cursor.execute("""
                    INSERT INTO invoice_payments (invoice_id, amount, payment_date, notes)
                    VALUES (?, ?, GETDATE(), ?)
                """, (invoice_id, -discount_amount, 'Discount applied'))

        # Process items
        for item in data['items']:
            cursor.execute("SELECT id, buy_price, sell_price, quantity FROM items WHERE barcode = ? OR '(,,)' + ISNULL(barcode2,'') + '(,,)' LIKE '%(,,)' + ? + '(,,)%'", [item['barcode'], item['barcode']])
            db_item = cursor.fetchone()
            
            new_quantity = item['quantity'] * item['quantity_type']
            
            if db_item:
                item_id = db_item[0]
                current_quantity = db_item[3] or 0
                
                # Record price changes
                if float(db_item[1]) != float(item['buy_price']) or float(db_item[2]) != float(item['sell_price']):
                    cursor.execute("""
                        INSERT INTO item_price_history (
                            item_id, old_buy_price, new_buy_price,
                            old_sell_price, new_sell_price, invoice_id
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        item_id, db_item[1], item['buy_price'],
                        db_item[2], item['sell_price'], invoice_id
                    ))
                
                # Update item
                cursor.execute("""
                    UPDATE items 
                    SET buy_price = ?, 
                        sell_price = ?, 
                        quantity = ?,
                        last_updated = GETDATE()
                    WHERE id = ?
                """, (
                    item['buy_price'],
                    item['sell_price'],
                    current_quantity + new_quantity,
                    item_id
                ))
            else:
                # Create new item
                cursor.execute("""
                    INSERT INTO items (
                        barcode, name, buy_price, sell_price, 
                        trader_id, quantity, last_updated, created_at
                    ) 
                    OUTPUT INSERTED.id
                    VALUES (?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())
                """, (
                    item['barcode'],
                    item['name'],
                    item['buy_price'],
                    item['sell_price'],
                    data['trader_id'],
                    new_quantity
                ))
                
                result = cursor.fetchone()
                if not result:
                    raise Exception(f"Failed to get ID for new item: {item['barcode']}")
                item_id = result[0]

            # Add invoice item
            cursor.execute("""
                INSERT INTO invoice_items (
                    invoice_id, item_id, quantity, quantity_type,
                    buy_price, sell_price, total_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                invoice_id, item_id,
                item['quantity'], item['quantity_type'],
                item['buy_price'], item['sell_price'],
                item['total']
            ))

        # Update shift totals
        cursor.execute("""
            UPDATE shifts
            SET invoices = invoices + ?
            WHERE id = ?
        """, [float(data['total_amount']), shift_id])

        cursor.execute("COMMIT")
        conn.commit()
        
        # Log the activity
        log_activity('invoice', f'Invoice #{invoice_id} created for trader {data["trader_id"]} - Amount: {data["total_amount"]}', 'invoices', invoice_id)
        
        return jsonify({'success': True, 'invoice_id': invoice_id})

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error saving invoice: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/get_categories_Invoices')
def get_categories_Invoices():
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM categories ORDER BY name")
        categories = [{'id': row[0], 'name': row[1]} for row in cursor.fetchall()]
        return jsonify(categories)
    except Exception as e:
        print(f"Error fetching categories: {str(e)}")
        return jsonify([])
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

            
# Add in #region Items Management

@app.route('/save_new_item', methods=['POST'])
def save_new_item():
    conn = None
    cursor = None
    try:
        data = request.json
        print("Received new item data:", data)  # Debug log
        
        conn = get_db()
        cursor = conn.cursor()

        # Get current user
        user_id = session.get('user_id')

        # Insert new item using IDENTITY
        cursor.execute("""
            INSERT INTO items (
                barcode, 
                name, 
                buy_price, 
                sell_price,
                quantity,
                last_updated,
                created_at,
                created_by
            ) 
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, GETDATE(), GETDATE(), ?)
        """, (
            data['barcode'],
            data['name'],
            data['buy_price'],
            data['sell_price'],
            0,  # Default quantity for new items
            user_id
        ))
        
        # Get the new item ID
        result = cursor.fetchone()
        if not result:
            raise Exception("Failed to get ID for new item")
        
        new_item_id = result[0]
        conn.commit()
        
        # Log the activity
        log_activity('create', f'New item created from invoice: {data["name"]} (Barcode: {data["barcode"]})', 'items', new_item_id)
        
        return jsonify({
            'success': True,
            'item_id': new_item_id,
            'message': 'Item saved successfully'
        })

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error saving new item: {str(e)}")  # Debug log
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

            
@app.route('/get_trader_suggestions')
def get_trader_suggestions():
    search = request.args.get('term', '')
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT t.id, t.name, t.phone, c.name as company_name
        FROM traders t
        LEFT JOIN companies c ON t.company = c.id
        WHERE t.name LIKE ? OR c.name LIKE ?
    """, (f'%{search}%', f'%{search}%'))
    traders = cursor.fetchall()
    db.close()
    
    return jsonify([{
        'id': trader[0],
        'name': trader[1],
        'phone': trader[2],
        'company_name': trader[3]
    } for trader in traders])


@app.route('/get_trader_companies/<int:trader_id>')
def get_trader_companies(trader_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT DISTINCT c.* 
        FROM companies c
        JOIN traders t ON t.company = c.id
        WHERE t.id = ?
    """, (trader_id,))
    companies = [dict(zip([column[0] for column in cursor.description], row)) 
                for row in cursor.fetchall()]
    db.close()
    return jsonify(companies)



#endregion

#region Inventory Audit

@app.route('/save_inventory_audit', methods=['POST'])
@login_required
def save_inventory_audit():
    data = request.get_json()
    items = data.get('items', [])
    approve_audit = data.get('approve', False)
    
    if not items:
        return jsonify({'success': False, 'message': 'No items provided'})
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Create audit session
        cursor.execute("""
            INSERT INTO inventory_audits (audit_date, user_id, approved)
            VALUES (GETDATE(), ?, ?)
        """, (session.get('user_id'), approve_audit))
        
        audit_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
        
        # Insert audit items
        for item in items:
            cursor.execute("""
                INSERT INTO inventory_audit_items (audit_id, item_id, expected_quantity, barcode, name, previous_quantity, actual_quantity, shortage, excess)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (audit_id, item['id'], item['current_quantity'], item.get('barcode', ''), item.get('name', ''), 
                  item['current_quantity'], item['actual_quantity'], item['shortage'], item['excess']))
        
        # If approve is requested, update item quantities
        if approve_audit:
            if 'approve_inventory_audit' not in session.get('permissions', []):
                return jsonify({'success': False, 'message': 'No permission to approve inventory audit'})
            
            for item in items:
                cursor.execute("""
                    UPDATE items 
                    SET quantity = ?, last_updated = GETDATE()
                    WHERE id = ?
                """, (item['actual_quantity'], item['id']))
        
        db.commit()
        return jsonify({'success': True, 'audit_id': audit_id, 'approved': approve_audit})
    
    except Exception as e:
        db.rollback()
        print(f"Error saving inventory audit: {e}")
        return jsonify({'success': False, 'message': 'Error saving audit'})
    finally:
        db.close()

@app.route('/approve_inventory_audit', methods=['POST'])
@login_required
def approve_inventory_audit():
    data = request.get_json()
    items = data.get('items', [])
    
    if not items:
        return jsonify({'success': False, 'message': 'No items provided'})
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Update item quantities
        for item in items:
            cursor.execute("""
                UPDATE items 
                SET quantity = ?, last_updated = GETDATE()
                WHERE id = ?
            """, (item['actual_quantity'], item['id']))
        
        # Mark audit as approved (assuming we have audit_id, but for simplicity, just update)
        # In a real app, you'd track the audit session
        
        db.commit()
        return jsonify({'success': True})
    
    except Exception as e:
        db.rollback()
        print(f"Error approving inventory audit: {e}")
        return jsonify({'success': False, 'message': 'Error approving audit'})
    finally:
        db.close()

@app.route('/get_all_items_for_audit')
@login_required
def get_all_items_for_audit():
    category_id = request.args.get('category_id', type=int)
    db = get_db()
    cursor = db.cursor()
    
    if category_id:
        cursor.execute("""
            SELECT id, barcode, name, quantity, category_id
            FROM items
            WHERE ISNULL(active, 1) = 1 AND category_id = ?
            ORDER BY name
        """, [category_id])
    else:
        cursor.execute("""
            SELECT id, barcode, name, quantity, category_id
            FROM items
            WHERE ISNULL(active, 1) = 1
            ORDER BY name
        """)
    
    items = [dict(zip([column[0] for column in cursor.description], row)) 
             for row in cursor.fetchall()]
    
    db.close()
    return jsonify(items)

@app.route('/audit_details/<int:audit_id>')
@login_required
def audit_details(audit_id):
    if 'previous_audits' not in session.get('permissions', []):
        return redirect(url_for('Home'))
    return render_template('audit_details.html')

@app.route('/previous_audits')
@login_required
def previous_audits():
    if 'previous_audits' not in session.get('permissions', []):
        return redirect(url_for('Home'))
    return render_template('previous_audits.html')

@app.route('/barcode_generator')
@login_required
def barcode_generator():
    if 'barcode_generator' not in session.get('permissions', []):
        return redirect(url_for('Home'))
    
    db = get_db()
    cursor = db.cursor()
    
    # Only include active traders
    cursor.execute("SELECT id, name FROM traders WHERE ISNULL(active, 1) = 1")
    traders = cursor.fetchall()
    
    cursor.execute("SELECT id, name FROM categories WHERE ISNULL(active,1) = 1")
    categories = cursor.fetchall()
    
    db.close()
    return render_template('barcode_generator.html', traders=traders, categories=categories)


@app.route('/get_printer')
@login_required
def get_printer():
    # Return saved printer name from settings table (single row expected)
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT printer_name FROM settings")
        row = cursor.fetchone()
        printer = row[0] if row else None
        return jsonify({'printer': printer})
    finally:
        db.close()


@app.route('/save_printer', methods=['POST'])
@login_required
def save_printer():
    if 'barcode_generator' not in session.get('permissions', []):
        return jsonify({'success': False, 'message': 'No permission'}), 403
    data = request.get_json() or {}
    printer = data.get('printer')
    if not printer:
        return jsonify({'success': False, 'message': 'No printer provided'})
    db = get_db()
    cursor = db.cursor()
    try:
        # Upsert into settings (if row exists update, else insert)
        cursor.execute("SELECT COUNT(*) FROM settings")
        if cursor.fetchone()[0] > 0:
            cursor.execute("UPDATE settings SET printer_name = ?", (printer,))
        else:
            cursor.execute("INSERT INTO settings (store_name, printer_name) VALUES (?, ?)", ('', printer))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        print('Error saving printer', e)
        return jsonify({'success': False, 'message': 'DB error'})
    finally:
        db.close()


@app.route('/create_item_from_barcode', methods=['POST'])
@login_required
def create_item_from_barcode():
    if 'barcode_generator' not in session.get('permissions', []):
        return jsonify({'success': False, 'message': 'No permission'}), 403
    data = request.get_json() or {}
    barcode = data.get('barcode')
    name = data.get('name')
    sell_price = data.get('sell_price', 0)
    quantity = data.get('quantity', 0)
    if not barcode or not name:
        return jsonify({'success': False, 'message': 'Missing fields'})
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM items WHERE barcode = ? OR '(,,)' + ISNULL(barcode2,'') + '(,,)' LIKE '%(,,)' + ? + '(,,)%'", (barcode, barcode))
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': 'Barcode already exists'})
        cursor.execute("INSERT INTO items (barcode, name, sell_price, quantity, created_at) VALUES (?, ?, ?, ?, GETDATE())",
                       (barcode, name, sell_price, quantity))
        created_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
        db.commit()
        return jsonify({'success': True, 'id': created_id})
    except Exception as e:
        db.rollback()
        print('Error creating item', e)
        return jsonify({'success': False, 'message': 'DB error'})
    finally:
        db.close()

@app.route('/create_item_with_barcode', methods=['POST'])
@login_required
def create_item_with_barcode():
    if 'barcode_generator' not in session.get('permissions', []):
        return jsonify({'success': False, 'message': 'No permission'}), 403
    
    data = request.get_json()
    
    # Validate required fields
    required = ['name', 'category_id', 'buy_price', 'sell_price', 'trader_id']
    for field in required:
        if field not in data or not data[field]:
            return jsonify({'success': False, 'message': f'Missing {field}'})
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Generate unique barcode
        while True:
            random_part = ''.join(random.choices('0123456789', k=8))
            barcode = f'-{random_part}'
            
            cursor.execute("SELECT COUNT(*) FROM items WHERE barcode = ? OR '(,,)' + ISNULL(barcode2,'') + '(,,)' LIKE '%(,,)' + ? + '(,,)%'", (barcode, barcode))
            if cursor.fetchone()[0] == 0:
                break
        
        # Create item
        cursor.execute("""
            INSERT INTO items (barcode, name, category_id, buy_price, sell_price, quantity, trader_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, GETDATE())
        """, (
            barcode,
            data['name'],
            data['category_id'],
            data['buy_price'],
            data['sell_price'],
            data.get('quantity', 0),
            data['trader_id']
        ))
        
        db.commit()
        return jsonify({'success': True, 'barcode': barcode})
    
    except Exception as e:
        db.rollback()
        print('Error creating item with barcode:', e)
        return jsonify({'success': False, 'message': 'DB error'})
    finally:
        db.close()

@app.route('/generate_barcodes', methods=['POST'])
@login_required
def generate_barcodes():
    if 'barcode_generator' not in session.get('permissions', []):
        return jsonify({'success': False, 'message': 'No permission'}), 403
    
    data = request.get_json()
    count = data.get('count', 1)
    
    if count < 1 or count > 50:
        return jsonify({'success': False, 'message': 'Invalid count'})
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        barcodes = []
        
        for _ in range(count):
            # Generate unique barcode starting with dash
            while True:
                # Generate a random 8-digit number
                random_part = ''.join(random.choices('0123456789', k=8))
                barcode = f'-{random_part}'
                
                # Check if barcode already exists
                cursor.execute("SELECT COUNT(*) FROM items WHERE barcode = ? OR '(,,)' + ISNULL(barcode2,'') + '(,,)' LIKE '%(,,)' + ? + '(,,)%'", (barcode, barcode))
                if cursor.fetchone()[0] == 0:
                    barcodes.append(barcode)
                    break

        # If request asked to create items, create them with provided template data
        create_template = data.get('create_template')
        created_items = []
        if create_template and isinstance(create_template, dict):
            # create_template should contain name, sell_price, quantity (optional) mapped to count
            # We'll create one item per barcode generated and return created item IDs
            for barcode in barcodes:
                try:
                    cursor.execute("INSERT INTO items (barcode, name, sell_price, quantity, created_at) VALUES (?, ?, ?, ?, GETDATE())",
                                   (barcode, create_template.get('name', ''), create_template.get('sell_price', 0), create_template.get('quantity', 0)))
                    created_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
                    created_items.append({'id': created_id, 'barcode': barcode})
                except Exception as e:
                    # ignore single failures and continue
                    print('Error creating item for barcode', barcode, e)

        return jsonify({'success': True, 'barcodes': barcodes, 'created_items': created_items})
    
    finally:
        db.close()

@app.route('/get_previous_audits')
@login_required
def get_previous_audits():
    if 'previous_audits' not in session.get('permissions', []):
        return jsonify({'error': 'Unauthorized'}), 403
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT 
            ia.id,
            ia.audit_date as created_at,
            ia.approved,
            COUNT(iai.id) as total_items,
            SUM(CASE WHEN iai.shortage > 0 THEN iai.shortage ELSE 0 END) as total_shortage,
            SUM(CASE WHEN iai.excess > 0 THEN iai.excess ELSE 0 END) as total_excess
        FROM inventory_audits ia
        LEFT JOIN inventory_audit_items iai ON ia.id = iai.audit_id
        GROUP BY ia.id, ia.audit_date, ia.approved
        ORDER BY ia.audit_date DESC
    """)
    
    audits = [dict(zip([column[0] for column in cursor.description], row)) 
              for row in cursor.fetchall()]
    
    db.close()
    return jsonify({'audits': audits})

@app.route('/get_audit_details/<int:audit_id>')
@login_required
def get_audit_details(audit_id):
    if 'previous_audits' not in session.get('permissions', []):
        return jsonify({'error': 'Unauthorized'}), 403
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        # Get audit info
        cursor.execute("""
            SELECT 
                ia.id,
                ia.audit_date as created_at,
                ia.approved,
                COUNT(iai.id) as total_items,
                SUM(CASE WHEN iai.shortage > 0 THEN iai.shortage ELSE 0 END) as total_shortage,
                SUM(CASE WHEN iai.excess > 0 THEN iai.excess ELSE 0 END) as total_excess
            FROM inventory_audits ia
            LEFT JOIN inventory_audit_items iai ON ia.id = iai.audit_id
            WHERE ia.id = ?
            GROUP BY ia.id, ia.audit_date, ia.approved
        """, (audit_id,))
        
        audit_row = cursor.fetchone()
        if not audit_row:
            return jsonify({'error': 'Audit not found'}), 404
            
        audit = dict(zip([column[0] for column in cursor.description], audit_row))
        
        # Get audit items
        cursor.execute("""
            SELECT 
                iai.barcode,
                i.name,
                iai.previous_quantity,
                iai.actual_quantity,
                iai.shortage,
                iai.excess
            FROM inventory_audit_items iai
            JOIN items i ON iai.item_id = i.id
            WHERE iai.audit_id = ?
            ORDER BY 
                CASE WHEN iai.shortage > 0 OR iai.excess > 0 THEN 0 ELSE 1 END,
                i.name
        """, (audit_id,))
        
        items = [dict(zip([column[0] for column in cursor.description], row)) 
                 for row in cursor.fetchall()]
        
        return jsonify({'audit': audit, 'items': items})
    
    finally:
        db.close()

#endregion





#region Sales Page (Home page)

@app.route('/get_quick_items')
def get_quick_items():
    cursor = None
    try:
        db = get_db()
        if not db:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cursor = db.cursor()
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
        print(f"Error in get_quick_items: {str(e)}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        if cursor:
            cursor.close()

@app.route('/get_item_Sell/<barcode>')
def get_item_Sell(barcode):
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT id, barcode, name, sell_price, quantity 
            FROM items 
            WHERE barcode = ? OR '(,,)' + ISNULL(barcode2,'') + '(,,)' LIKE '%(,,)' + ? + '(,,)%'
        """, [barcode, barcode])

        item = cursor.fetchone()

        if item:
            return jsonify({
                'id': int(item[0]),
                'barcode': str(item[1]),
                'name': item[2],
                'sell_price': float(item[3]),
                'quantity': int(item[4]) if item[4] is not None else 0
            })
        else:
            return jsonify({'error': 'Item not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if db:
            db.close()


@app.route('/search_items/<term>')
def search_items(term):
    try:
        db = get_db()
        cursor = db.cursor()
        
        search_term = term.strip()
        is_numeric = search_term.isdigit()
        
        if is_numeric:
            # Numeric search: exact barcode/barcode2 match first
            cursor.execute("""
                SELECT barcode, name, sell_price 
                FROM items 
                WHERE barcode = ? OR barcode2 = ?
                   OR barcode2 LIKE ? + '(,,)%'
                   OR barcode2 LIKE '%(,,)' + ?
                   OR barcode2 LIKE '%(,,)' + ? + '(,,)%'
                ORDER BY name
            """, [search_term, search_term, search_term, search_term, search_term])
            
            items = cursor.fetchall()
            
            # Fallback to partial match if no exact match
            if not items:
                cursor.execute("""
                    SELECT TOP 10 barcode, name, sell_price 
                    FROM items 
                    WHERE barcode LIKE ? OR ISNULL(barcode2,'') LIKE ?
                    ORDER BY name
                """, [f'%{search_term}%', f'%{search_term}%'])
                items = cursor.fetchall()
        else:
            # Text search: flexible word matching
            # Split search term into words
            words = search_term.split()
            
            if len(words) == 1:
                # Single word search
                cursor.execute("""
                    SELECT TOP 10 barcode, name, sell_price 
                    FROM items 
                    WHERE name LIKE ? OR barcode LIKE ? OR ISNULL(barcode2,'') LIKE ?
                    ORDER BY name
                """, [f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'])
                items = cursor.fetchall()
            else:
                # Multi-word search: all words must exist in name (any order)
                # Build WHERE clause with AND conditions
                where_conditions = []
                params = []
                for word in words:
                    where_conditions.append("name LIKE ?")
                    params.append(f'%{word}%')
                
                where_clause = " AND ".join(where_conditions)
                
                cursor.execute(f"""
                    SELECT TOP 10 barcode, name, sell_price 
                    FROM items 
                    WHERE {where_clause}
                    ORDER BY name
                """, params)
                items = cursor.fetchall()
        
        # Convert to list of dictionaries
        result = [{
            'barcode': str(item[0]),
            'name': item[1],
            'sell_price': float(item[2])
        } for item in items]
        
        return jsonify(result)
            
    except Exception as e:
        print(f"Search error: {str(e)}")  # Log the error
        return jsonify([])  # Return empty array instead of error
    finally:
        if db:
            db.close()



# Save receipt
@app.route('/save_sale', methods=['POST'])
def save_sale():
    data = request.json
    conn = get_db()
    global last_sale_id
    if not conn:
        return jsonify({"success": False, "error": "Database connection failed"}), 500

    cursor = conn.cursor()
    try:
        print("\n1. Transaction started")
        cursor.execute("BEGIN TRANSACTION")
        
        # Check for active shift
        cursor.execute("""
            SELECT TOP 1 id FROM shifts WHERE status = 'active' ORDER BY start_time DESC
        """)
        
        shift_row = cursor.fetchone()
        if not shift_row:
            raise Exception("لا يوجد وردية نشطة")
        
        shift_id = shift_row[0]
        print(f"\n2. Found active shift: ID={shift_id}")
        
        # Get next sale number
        cursor.execute("""
            SELECT MAX(sale_number) + 1
            FROM (
                SELECT MAX(sale_number) as sale_number 
                FROM sales 
                WHERE shift_id = ?
                UNION ALL
                SELECT MAX(sale_number)
                FROM daily_sales 
                WHERE shift_id = ?
            ) combined
        """, [shift_id, shift_id])
        
        shift_sale_number = cursor.fetchone()[0] or 1  # Default to 1 if no previous sales
        print(f"\n2.1 Next sale number for shift: {shift_sale_number}")

        # Determine status based on delivery information
        has_delivery_info = all([
            data.get('customer_phone'),
            data.get('customer_name'),
            data.get('address_line1')
        ])
        sale_status = 'pending' if has_delivery_info else 'completed'

        # Get current user
        user_id = session.get('user_id')

        # Common sales data
        sales_data = (
            shift_id,
            shift_sale_number,
            data['total_amount'],
            data['subtotal'],
            data.get('discount_amount', 0),
            data.get('delivery_fee', 0),
            data['final_amount'],
            data['payment_method'],
            data.get('cash_box_id'),
            data.get('customer_name') or None,
            data.get('customer_phone') or None,
            data.get('address_line1') or None,
            data.get('address_line2') or None,
            data.get('address_line3') or None,
            data.get('paid_amount', 0),
            data.get('residual', 0),
            data.get('delivery_worker_id'),
            data.get('delivery_worker_name'),
            sale_status,
            user_id
        )

        # Insert into regular sales
        cursor.execute("""
            INSERT INTO sales (
                shift_id, sale_number, total_amount, subtotal,
                discount_amount, delivery_fee, final_amount,
                payment_method, cash_box_id, customer_name, customer_phone,
                address_line1, address_line2, address_line3,
                paid_amount, residual_amount, delivery_worker_id,
                delivery_worker_name, status, created_at, user_id
            )
            OUTPUT INSERTED.id, INSERTED.sale_number
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                GETDATE(), ?)
        """, sales_data)

        sale_result = cursor.fetchone()
        if not sale_result:
            raise Exception("فشل إنشاء الفاتورة")

        sale_id, sale_number = sale_result
        last_sale_id = sale_id

        # Insert into daily_sales
        cursor.execute("""
            INSERT INTO daily_sales (
                shift_id, sale_number, total_amount, subtotal,
                discount_amount, delivery_fee, final_amount,
                payment_method, cash_box_id, customer_name, customer_phone,
                address_line1, address_line2, address_line3,
                paid_amount, residual_amount, delivery_worker_id,
                delivery_worker_name, status, created_at, user_id
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                GETDATE(), ?)
        """, sales_data)

        daily_sale_result = cursor.fetchone()
        if not daily_sale_result:
            raise Exception("فشل إنشاء الفاتورة اليومية")

        daily_sale_id = daily_sale_result[0]
        # Track last created daily sale id so client can request printing
        last_sale_id = daily_sale_id

        # Update the shifts.sales aggregate so UI/summary shows running total
        try:
            cursor.execute("""
                UPDATE shifts
                SET sales = ISNULL(sales, 0) + ?
                WHERE id = ?
            """, (data['final_amount'], shift_id))
        except Exception as e:
            print(f"Warning: failed to update shifts.sales: {e}")

        # Update shift_cash_boxes if cash_box_id is provided AND status is completed/done/paid
        cash_box_id = data.get('cash_box_id')
        if cash_box_id and sale_status.lower() in ['completed', 'done', 'paid']:
            try:
                # Check if record exists for this shift and cash box
                cursor.execute("""
                    SELECT id, amount FROM shift_cash_boxes 
                    WHERE shift_id = ? AND cash_box_id = ?
                """, (shift_id, cash_box_id))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing record
                    cursor.execute("""
                        UPDATE shift_cash_boxes
                        SET amount = amount + ?
                        WHERE shift_id = ? AND cash_box_id = ?
                    """, (data['final_amount'], shift_id, cash_box_id))
                else:
                    # Insert new record
                    cursor.execute("""
                        INSERT INTO shift_cash_boxes (shift_id, cash_box_id, amount)
                        VALUES (?, ?, ?)
                    """, (shift_id, cash_box_id, data['final_amount']))
                
                print(f"Updated shift_cash_boxes: shift={shift_id}, box={cash_box_id}, amount={data['final_amount']}, status={sale_status}")
            except Exception as e:
                print(f"Warning: failed to update shift_cash_boxes: {e}")

        # Validate items
        if 'items' not in data or not isinstance(data['items'], list) or not data['items']:
            raise Exception("لم يتم إرسال أي عناصر للبيع")

        # ===== QUANTITY VALIDATION: Check stock before processing =====
        for item in data['items']:
            cursor.execute("""
                SELECT id, name, quantity FROM items 
                WHERE barcode = ? OR '(,,)' + ISNULL(barcode2,'') + '(,,)' LIKE '%(,,)' + ? + '(,,)%'
            """, [item['barcode'], item['barcode']])
            
            row = cursor.fetchone()
            if row is None:
                raise Exception(f"المنتج غير موجود: {item['barcode']}")
            
            item_id, item_name, available_quantity = row
            sale_quantity = item['quantity']
            
            # Check if item has stock
            if available_quantity is None or available_quantity <= 0:
                raise Exception(f"المنتج '{item_name}' غير متوفر في المخزون (الكمية: {available_quantity or 0})")
            
            # Check if sale quantity exceeds available stock
            if sale_quantity > available_quantity:
                raise Exception(f"الكمية المطلوبة للمنتج '{item_name}' ({sale_quantity}) أكبر من الكمية المتوفرة ({available_quantity})")
        
        # ===== END VALIDATION =====

        # Process each item (update quantities)
        for item in data['items']:
            cursor.execute("""
                SELECT id, quantity FROM items WHERE barcode = ? OR '(,,)' + ISNULL(barcode2,'') + '(,,)' LIKE '%(,,)' + ? + '(,,)%'
            """, [item['barcode'], item['barcode']])
            
            row = cursor.fetchone()
            if row is None:
                raise Exception(f"المنتج غير موجود: {item['barcode']}")
                
            item_id, current_quantity = row
            new_quantity = (current_quantity or 0) - item['quantity']

            # Update item quantity
            cursor.execute("""
                UPDATE items 
                SET quantity = ?, last_updated = GETDATE()
                WHERE id = ?
            """, (new_quantity, item_id))
            
            # Common item data
            item_data = (
                item_id,
                item['barcode'],
                item['name'],
                item['quantity'],
                item['unit_price'],
                item['total_price']
            )

            # Insert into regular sale_items
            cursor.execute("""
                INSERT INTO sale_items (
                    sale_id, item_id, barcode, item_name,
                    quantity, unit_price, total_price
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sale_id,) + item_data)

            # Insert into daily_sale_items
            cursor.execute("""
                INSERT INTO daily_sale_items (
                    sale_id, item_id, barcode, item_name,
                    quantity, unit_price, total_price
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (daily_sale_id,) + item_data)

        cursor.execute("COMMIT")
        conn.commit()
        print("\n5. Transaction committed successfully")

        # Log the activity
        log_activity('sale', f'Sale #{sale_number} created - Amount: {data["final_amount"]} - Method: {data["payment_method"]}', 'sales', sale_id)

        return jsonify({
            'success': True,
            'sale_id': sale_id,
            'daily_sale_id': daily_sale_id,
            'sale_number': sale_number,
            'message': 'تم حفظ الفاتورة بنجاح'
        })

    except Exception as e:
        if conn:
            try:
                cursor.execute("ROLLBACK")
                conn.rollback()
                print(f"\nERROR: Transaction rolled back: {str(e)}")
            except:
                pass
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            g.db_closed = True
@app.route('/check_active_shift', methods=['GET'])
def check_active_shift():
    conn = None
    cursor = None
    try:
        conn = get_db()
        if not conn:
            return jsonify({
                'success': False,
                'error': 'Database connection failed'
            }), 500

        cursor = conn.cursor()
        
        # Check for active shift
        cursor.execute("""
            SELECT id FROM shifts 
            WHERE status = 'active' 
            ORDER BY start_time DESC
        """)
        
        active_shift = cursor.fetchone()
        
        if not active_shift:
            # Create new shift
            cursor.execute("""
                INSERT INTO shifts (cashier_name, status)
                VALUES (?, 'active')
            """, ('Default Cashier',))
            
            conn.commit()
            return jsonify({
                'success': True, 
                'message': 'تم إنشاء وردية جديدة'
            })
            
        return jsonify({
            'success': True, 
            'message': 'يوجد وردية نشطة'
        })
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        print(f"Error checking shift: {str(e)}")
        return jsonify({
            'success': False, 
            'error': str(e)
        }), 500
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass

@app.route('/print_receipt/<int:daily_sale_id>')
def print_receipt(daily_sale_id):
    print(f"Attempting to print receipt for sale_id: {daily_sale_id}")
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get printer settings
        cursor.execute("SELECT printer_name, store_name, store_phone, store_address, receipt_footer FROM settings WHERE id = 1")
        settings = cursor.fetchone()
        if not settings:
            raise Exception("لم يتم العثور على إعدادات الطابعة")
            
        settings_dict = {
            'printer_name': settings[0],
            'store_name': settings[1],
            'store_phone': settings[2],
            'store_address': settings[3],
            'receipt_footer': settings[4]
        }
        
        if not settings_dict['printer_name']:
            raise Exception("لم يتم تحديد طابعة")
            
        # Get sale details
        cursor.execute("""
            SELECT s.id, s.sale_number, s.total_amount, s.discount_amount, 
                s.delivery_fee, s.final_amount, s.created_at, s.paid_amount,
                si.barcode, si.item_name, si.quantity, 
                si.unit_price, si.total_price,
                s.customer_name, s.customer_phone,
                s.address_line1, s.address_line2, s.address_line3
            FROM daily_sales s
            LEFT JOIN daily_sale_items si ON s.id = si.sale_id
            WHERE s.id = ?
        """, [daily_sale_id])
        sale_items = cursor.fetchall()
        if not sale_items:
            raise Exception("لم يتم العثور على الفاتورة")

        # Setup printer
        hprinter = win32print.OpenPrinter(settings_dict['printer_name'])
        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(settings_dict['printer_name'])
        dc.StartDoc('Receipt')
        dc.StartPage()

        # Get printer dimensions
        dpi_x = dc.GetDeviceCaps(88)  # LOGPIXELSX
        page_width = dc.GetDeviceCaps(8)  # PHYSICALWIDTH
        margin = 5
        right_edge = page_width - margin
        x_center = (right_edge + margin) // 2

        # Create fonts
        header_font = win32ui.CreateFont({
            'name': 'Arial',
            'height': 60,  # Increased from 40
            'weight': 700
        })
        normal_font = win32ui.CreateFont({
            'name': 'Arial',
            'height': 35,  # Increased from 25
            'weight': 400
        })
        bold_font = win32ui.CreateFont({
            'name': 'Arial',
            'height': 45,  # Increased from 30
            'weight': 700
        })

        # Adjust initial position and spacing
        y = -10  # Increased from 100
        line_spacing = 40  # Added line spacing variable

        # Print store name centered
        dc.SelectObject(header_font)
        text = settings_dict['store_name']
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(x_center - text_width // 2, y, text)

        # Print sale number centered with more spacing
        y += 70  # Increased from 50
        dc.SelectObject(normal_font)
        text = f"رقم الفاتورة: {sale_items[0][1]}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(x_center - text_width // 2, y, text)

        # Print date centered
        y += 40  # Increased from 30
        text = datetime.now().strftime("%Y-%m-%d %H:%M")
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(x_center - text_width // 2, y, text)
        if sale_items[0][14] or sale_items[0][15] or sale_items[0][16] or sale_items[0][17]:  # If phone or any address line exists
            y += 60  # Add space for customer details
            dc.SelectObject(normal_font)

            # Print customer name if exists
            if sale_items[0][13]:  # customer_name
                text = f"اسم العميل: {sale_items[0][13]}"
                text_width = dc.GetTextExtent(text)[0]
                dc.TextOut(right_edge - text_width - 10, y, text)
                y += 40

            # Print phone if exists
            if sale_items[0][14]:  # customer_phone
                text = f"رقم الهاتف: {sale_items[0][14]}"
                text_width = dc.GetTextExtent(text)[0]
                dc.TextOut(right_edge - text_width - 10, y, text)
                y += 40

            # Print addresses if they exist
            if sale_items[0][15]:  # address_line1
                text = f"العنوان: {sale_items[0][15]}"
                text_width = dc.GetTextExtent(text)[0]
                dc.TextOut(right_edge - text_width - 10, y, text)
                y += 40

            if sale_items[0][16]:  # address_line2
                text = sale_items[0][16]
                text_width = dc.GetTextExtent(text)[0]
                dc.TextOut(right_edge - text_width - 10, y, text)
                y += 40

            if sale_items[0][17]:  # address_line3
                text = sale_items[0][17]
                text_width = dc.GetTextExtent(text)[0]
                dc.TextOut(right_edge - text_width - 10, y, text)
                y += 40

            # Add a separator line after customer details
            dc.MoveTo(margin, y)
            dc.LineTo(right_edge, y)
            y += 20

        # Draw table with adjusted dimensions
        y += 60  # Increased spacing before table
        # Reversed order of headers for right-to-left
        headers = ["المنتج", "الكمية", "السعر", "الإجمالي"]
        
        # Calculate dynamic widths
        total_width = right_edge - margin
        fixed_col_width = 120  # Width for quantity, price, and total columns
        # Name column gets remaining space
        name_col_width = total_width - (fixed_col_width * 3)
        
        # Column widths from right to left
        col_widths = [name_col_width, fixed_col_width, fixed_col_width, fixed_col_width]
        x_positions = []
        current_x = right_edge

        # Draw table header background
        header_height = 45  # Increased height for better readability
        dc.MoveTo(margin, y - 5)
        dc.LineTo(right_edge, y - 5)

        # Print headers and draw vertical lines
        for i, header in enumerate(headers):
            current_x -= col_widths[i]
            x_positions.append(current_x)
            
            # Draw vertical lines for full table height
            dc.MoveTo(current_x, y - 5)
            dc.LineTo(current_x, y + header_height)
            
            text_width = dc.GetTextExtent(header)[0]
            x_pos = current_x + (col_widths[i] - text_width) // 2
            dc.TextOut(x_pos, y, header)

        # Draw rightmost and leftmost vertical lines
        dc.MoveTo(right_edge, y - 5)
        dc.LineTo(right_edge, y + header_height)
        dc.MoveTo(margin, y - 5)
        dc.LineTo(margin, y + header_height)

        # Update y position for items
        y += header_height
        dc.MoveTo(margin, y)
        dc.LineTo(right_edge, y)
        # Print items with consistent vertical lines
        for item in sale_items:
            item_height = 45  # Row height
            
            # Draw vertical lines for this row
            for x in [margin] + x_positions + [right_edge]:
                dc.MoveTo(x, y)
                dc.LineTo(x, y + item_height)
            
            current_y = y + 5  # Add padding within cell

            # Format quantity correctly
            quantity = item[10]
            if quantity == int(quantity):  # If it's a whole number, print without decimals
                quantity_text = f"{int(quantity)}"
            else:  # If it has decimals, keep the original format
                quantity_text = f"{quantity:.2f}"
            
            # Print item data in correct order (right to left)

            # Item name (right-aligned, rightmost column)
            text = str(item[9])[:30]  # Truncate long names
            text_width = dc.GetTextExtent(text)[0]
            # Align the item name to the right of the cell
            dc.TextOut(x_positions[0] + col_widths[0] - text_width - 10, current_y, text)

            # Quantity (centered, second column)
            text = quantity_text
            text_width = dc.GetTextExtent(text)[0]
            dc.TextOut(x_positions[1] + (fixed_col_width - text_width) // 2, current_y, text)  

            # Unit price (centered, third column)
            text = f"{item[11]:.2f}"
            text_width = dc.GetTextExtent(text)[0]
            dc.TextOut(x_positions[2] + (fixed_col_width - text_width) // 2, current_y, text)  

            # Total price (centered, leftmost column)
            text = f"{item[12]:.2f}"
            text_width = dc.GetTextExtent(text)[0]
            dc.TextOut(x_positions[3] + (fixed_col_width - text_width) // 2, current_y, text)  

            # Draw horizontal line
            y += item_height
            dc.MoveTo(margin, y)
            dc.LineTo(right_edge, y)

        y += 15  # Space after items table
        dc.SelectObject(bold_font)

        # First line: Total and Delivery Fee
        total_with_delivery = (sale_items[0][2] or 0) + (sale_items[0][4] or 0)
        text_total = f"الإجمالي : {total_with_delivery:.2f}"
        text_width_total = dc.GetTextExtent(text_total)[0]
        dc.TextOut(right_edge - text_width_total - 10, y, text_total)

        if sale_items[0][4]:  # If delivery fee exists
            text_delivery = f"خدمة التوصيل: {sale_items[0][4]:.2f}"
            text_width_delivery = dc.GetTextExtent(text_delivery)[0]
            dc.TextOut(x_center - text_width_delivery - 10, y, text_delivery)

        # Second line: Discount and Final Amount
        y += 50
        if sale_items[0][3] > 0:  # If discount exists
            text_discount = f"الخصم: {sale_items[0][3]:.2f}"
            text_width_discount = dc.GetTextExtent(text_discount)[0]
            dc.TextOut(right_edge - text_width_discount - 10, y, text_discount)

            text_final = f"الصافي: {sale_items[0][5]:.2f}"
            text_width_final = dc.GetTextExtent(text_final)[0]
            dc.TextOut(x_center - text_width_final - 10, y, text_final)

        # Third line: Paid Amount and Residual (if paid amount exists)
        paid_amount = sale_items[0][7]  # Get paid_amount from the query result
        if paid_amount and paid_amount > 0:
            y += 50
            residual = paid_amount - sale_items[0][5]  # Paid - Final amount

            text_paid = f"المدفوع: {paid_amount:.2f}"
            text_width_paid = dc.GetTextExtent(text_paid)[0]
            dc.TextOut(right_edge - text_width_paid - 10, y, text_paid)

            text_residual = f"الباقي: {residual:.2f}"
            text_width_residual = dc.GetTextExtent(text_residual)[0]
            dc.TextOut(x_center - text_width_residual - 10, y, text_residual)

        # Print contact info at bottom
        y += 50
        dc.SelectObject(normal_font)
        
        if settings_dict['store_phone']:
            text = f"الهاتف: {settings_dict['store_phone']}"
            text_width = dc.GetTextExtent(text)[0]
            dc.TextOut(x_center - text_width // 2, y, text)
            y += 30

        if settings_dict['store_address']:
            text = f"العنوان: {settings_dict['store_address']}"
            text_width = dc.GetTextExtent(text)[0]
            dc.TextOut(x_center - text_width // 2, y, text)
            y += 30

        # Print footer
        if settings_dict['receipt_footer']:
            y += 20
            text = settings_dict['receipt_footer']
            text_width = dc.GetTextExtent(text)[0]
            dc.TextOut(x_center - text_width // 2, y, text)

        dc.EndPage()
        dc.EndDoc()
        dc.DeleteDC()
        win32print.ClosePrinter(hprinter)

        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Print error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
@app.route('/get_last_sale_id', methods=['GET'])
def get_last_sale_id():
    try:
        # If in-memory value exists return it
        if last_sale_id:
            return jsonify({
                'success': True,
                'sale_id': last_sale_id,
                'daily_sale_id': last_sale_id
            })

        # Fallback: try to fetch the latest daily sale id from DB
        try:
            conn = get_db()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT TOP 1 id FROM daily_sales ORDER BY created_at DESC")
                row = cursor.fetchone()
                if row:
                    fetched_id = row[0]
                    # update in-memory cache for subsequent calls
                    globals()['last_sale_id'] = fetched_id
                    cursor.close()
                    try:
                        conn.close()
                    except Exception:
                        pass
                    return jsonify({
                        'success': True,
                        'sale_id': fetched_id,
                        'daily_sale_id': fetched_id
                    })
                cursor.close()
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as db_e:
            print(f"Error fetching last sale from DB: {db_e}")

        return jsonify({
            'success': False,
            'error': 'لا توجد فاتورة سابقة'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/print_last_receipt', methods=['POST'])
def print_last_receipt():
    try:
        data = None
        try:
            data = request.get_json(silent=True) or {}
        except Exception:
            data = {}

        # Allow client to explicitly pass an id, otherwise use last_sale_id
        sale_to_print = data.get('daily_sale_id') or last_sale_id

        if not sale_to_print:
            raise Exception("لا توجد فاتورة سابقة للطباعة")

        # Reuse existing print_receipt function
        return print_receipt(sale_to_print)
        
    except Exception as e:
        print(f"Print error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/save_and_print', methods=['POST'])
def save_and_print():
    try:
        # First save the sale
        save_result = save_sale()
        save_data = save_result.get_json()
        
        if not save_data.get('success'):
            raise Exception(save_data.get('error', 'Failed to save sale'))
            
        # Then print it
        sale_id = save_data.get('sale_id')
        if not sale_id:
            raise Exception("No sale ID returned from save operation")
            
        return print_receipt(sale_id)
        
    except Exception as e:
        print(f"Save and print error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/get_phone_suggestions/<prefix>')
@login_required
def get_phone_suggestions(prefix):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT Top 10 phone_number 
            FROM customers 
            WHERE phone_number LIKE ? 
            ORDER BY lastorder DESC, created_at DESC
        """, [f"{prefix}%"])

        
        suggestions = [row[0] for row in cursor.fetchall()]
        return jsonify({'suggestions': suggestions})
    finally:
        cursor.close()
        conn.close()


@app.route('/get_deleted_items')
@login_required
@permission_required('settings')
def get_deleted_items():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, barcode, name FROM items WHERE ISNULL(active,1) = 0 ORDER BY id DESC")
        rows = cursor.fetchall()
        items = [{'id': r[0], 'barcode': r[1], 'name': r[2]} for r in rows]
        return jsonify(items)
    finally:
        cursor.close()
        conn.close()


@app.route('/restore_item', methods=['POST'])
@login_required
@permission_required('settings')
def restore_item():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE items SET active = 1 WHERE id = ?", (data.get('id'),))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/get_deleted_traders')
@login_required
@permission_required('settings')
def get_deleted_traders():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, phone FROM traders WHERE ISNULL(active,1) = 0 ORDER BY id DESC")
        rows = cursor.fetchall()
        traders = [{'id': r[0], 'name': r[1], 'phone': r[2]} for r in rows]
        return jsonify(traders)
    finally:
        cursor.close()
        conn.close()


@app.route('/restore_trader', methods=['POST'])
@login_required
@permission_required('settings')
def restore_trader():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE traders SET active = 1 WHERE id = ?", (data.get('id'),))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/get_deleted_companies')
@login_required
@permission_required('settings')
def get_deleted_companies():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, phone FROM companies WHERE ISNULL(active,1) = 0 ORDER BY id DESC")
        rows = cursor.fetchall()
        companies = [{'id': r[0], 'name': r[1], 'phone': r[2]} for r in rows]
        return jsonify(companies)
    finally:
        cursor.close()
        conn.close()


@app.route('/restore_company', methods=['POST'])
@login_required
@permission_required('settings')
def restore_company():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE companies SET active = 1 WHERE id = ?", (data.get('id'),))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/get_deleted_categories')
@login_required
@permission_required('settings')
def get_deleted_categories():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name FROM categories WHERE ISNULL(active,1) = 0 ORDER BY id DESC")
        rows = cursor.fetchall()
        cats = [{'id': r[0], 'name': r[1]} for r in rows]
        return jsonify(cats)
    finally:
        cursor.close()
        conn.close()


@app.route('/restore_category', methods=['POST'])
@login_required
@permission_required('settings')
def restore_category():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE categories SET active = 1 WHERE id = ?", (data.get('id'),))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/get_customer_data/<phone>')
@login_required
def get_customer_data(phone):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT name, address_line1, address_line2, address_line3
            FROM customers 
            WHERE phone_number = ?
        """, [phone])
        
        row = cursor.fetchone()
        if row:
            return jsonify({
                'success': True,
                'customer': {
                    'name': row[0],
                    'address_line1': row[1],
                    'address_line2': row[2],
                    'address_line3': row[3]
                }
            })
        return jsonify({
            'success': False,
            'message': 'Customer not found'
        })
    finally:
        cursor.close()
        conn.close()


@app.route('/save_customer', methods=['POST'])
@login_required
def save_customer():
    data = request.get_json() or {}
    phone = data.get('phone')
    name = data.get('name')
    addr1 = data.get('address_line1')
    addr2 = data.get('address_line2')
    addr3 = data.get('address_line3')

    if not phone:
        return jsonify({'success': False, 'error': 'Phone is required'}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM customers WHERE phone_number = ?", [phone])
        row = cursor.fetchone()
        if row:
            # Update
            cursor.execute("""
                UPDATE customers
                SET name = ?, address_line1 = ?, address_line2 = ?, address_line3 = ?, updated_at = GETDATE()
                WHERE phone_number = ?
            """, [name, addr1, addr2, addr3, phone])
            conn.commit()
            return jsonify({'success': True, 'action': 'updated'})
        else:
            # Insert
            cursor.execute("""
                INSERT INTO customers (phone_number, name, address_line1, address_line2, address_line3, created_at)
                VALUES (?, ?, ?, ?, ?, GETDATE())
            """, [phone, name, addr1, addr2, addr3])
            conn.commit()
            return jsonify({'success': True, 'action': 'created'})
    except Exception as e:
        conn.rollback()
        print(f"Error saving customer: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/get_customer_history/<phone>', methods=['GET'])
@login_required
def get_customer_history(phone):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get customer info
        cursor.execute("""
            SELECT name, phone_number, address_line1, address_line2, address_line3
            FROM customers 
            WHERE phone_number = ?
        """, [phone])
        
        customer = cursor.fetchone()
        if not customer:
            print(f"No customer found for phone: {phone}")  # Debug log
            return jsonify({'success': False, 'error': 'Customer not found'})
            
        customer_data = {
            'name': customer[0],
            'phone': customer[1],  # Fixed typo here
            'address_line1': customer[2],
            'address_line2': customer[3],
            'address_line3': customer[4]
        }
        
        # Get customer's order history with debug logging
        print(f"Fetching orders for phone: {phone}")  # Debug log
        cursor.execute("""
            SELECT s.id, s.sale_number, s.created_at, s.final_amount,
                   s.address_line1, s.status, s.delivery_worker_name, s.delivery_worker_id
            FROM sales s
            WHERE s.customer_phone = ?
            ORDER BY s.created_at DESC
        """, [phone])
        
        orders = [{
            'id': row[0],
            'sale_number': row[1],
            'created_at': row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else None,
            'final_amount': float(row[3]) if row[3] else 0.0,
            'address_line1': row[4],
            'status': row[5],
            'delivery_worker_name': row[6] or 'لم يتم التعيين',
            'delivery_worker_id': row[7]
        } for row in cursor.fetchall()]
        
        print(f"Found {len(orders)} orders")  # Debug log
        
        return jsonify({
            'success': True,
            'customer': customer_data,
            'orders': orders
        })
        
    except Exception as e:
        print(f"Error getting customer history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
        print("Database connection closed")  # Debug log



@app.route('/get_order_details/<int:order_id>', methods=['GET'])
@login_required
def get_order_details(order_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get order details
        cursor.execute("""
            SELECT s.id, s.sale_number, s.created_at, s.final_amount,
                   s.total_amount, s.discount_amount, s.delivery_fee,
                   s.customer_name, s.customer_phone, s.address_line1,
                   s.payment_method, s.status
            FROM daily_sales s
            WHERE s.id = ?
        """, [order_id])
        
        order = cursor.fetchone()
        if not order:
            return jsonify({'success': False, 'error': 'Order not found'}), 404
            
        order_data = {
            'id': order[0],
            'sale_number': order[1],
            'created_at': order[2].strftime('%Y-%m-%d %H:%M:%S') if order[2] else None,
            'final_amount': float(order[3]) if order[3] else 0.0,
            'total_amount': float(order[4]) if order[4] else 0.0,
            'discount_amount': float(order[5]) if order[5] else 0.0,
            'delivery_fee': float(order[6]) if order[6] else 0.0,
            'customer_name': order[7],
            'customer_phone': order[8],
            'address_line1': order[9],
            'payment_method': order[10],
            'status': order[11]
        }
        
        # Get order items
        cursor.execute("""
            SELECT si.id, i.name, si.quantity, si.unit_price, si.total_price
            FROM sale_items si
            JOIN items i ON si.item_id = i.id
            WHERE si.sale_id = ?
        """, [order_id])
        
        items = [{
            'id': row[0],
            'name': row[1],
            'quantity': float(row[2]) if row[2] else 0.0,
            'unit_price': float(row[3]) if row[3] else 0.0,
            'total_price': float(row[4]) if row[4] else 0.0
        } for row in cursor.fetchall()]
        
        return jsonify({
            'success': True,
            'order': order_data,
            'items': items
        })
        
    except Exception as e:
        print(f"Error getting order details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()



#endregion








#region Delivery

@app.route('/delivery')
@login_required
def delivery_page():
    return render_template('delivery.html')


@app.route('/get_pending_orders')
@login_required
def get_pending_orders():
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Updated query to include all address lines and delivery worker
        cursor.execute("""
            SELECT 
                ds.id,
                ds.sale_number,
                ds.final_amount,
                ds.delivery_fee,
                ds.created_at,
                ds.customer_name,
                ds.customer_phone,
                ds.address_line1,
                ds.address_line2,
                ds.address_line3,
                ds.status,
                ds.delivery_worker_name,
                ds.delivery_worker_id
            FROM daily_sales ds
            WHERE (ds.status = 'pending' OR ds.status = 'assigned')
            ORDER BY ds.created_at DESC
        """)
        
        orders = []
        for row in cursor.fetchall():
            # Combine address lines with spaces between non-empty parts
            address_parts = [part for part in [row[7], row[8], row[9]] if part]
            full_address = ' - '.join(address_parts) if address_parts else '-'
            # Format the created_at timestamp
            created_at = row[4].strftime('%Y-%m-%d %I:%M %p') if row[4] else '-'

            order = {
                'id': row[0],
                'sale_number': row[1],
                'final_amount': float(row[2]),
                'delivery_fee': float(row[3]),
                'created_at': created_at,
                'customer_name': row[5],
                'customer_phone': row[6],
                'status': row[10],
                'delivery_worker_name': row[11] or 'لم يتم التعيين',
                'delivery_worker_id': row[12]

            }
            orders.append(order)

        # Return the orders list (after processing all rows)
        return jsonify({'success': True, 'orders': orders})

    except Exception as e:
        print(f"Error fetching pending deliveries: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_order_details_dlev/<int:order_id>')
@login_required
def get_order_details_dlev(order_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        # Try to get order details from daily_sales (current shift)
        cursor.execute("""
            SELECT 
                ds.id,
                ds.sale_number,
                ds.total_amount,
                ds.final_amount,
                ds.delivery_fee,
                ds.created_at,
                ds.customer_name,
                ds.customer_phone,
                ds.address_line1,
                ds.address_line2,
                ds.address_line3,
                ds.payment_method,
                ds.status
            FROM daily_sales ds
            WHERE ds.id = ?
        """, [order_id])

        order_row = cursor.fetchone()

        items = []
        # If found in daily_sales, load daily_sale_items
        if order_row:
            cursor.execute("""
                SELECT 
                    dsi.item_name,
                    dsi.quantity,
                    dsi.unit_price,
                    dsi.total_price
                FROM daily_sale_items dsi
                WHERE dsi.sale_id = ?
            """, [order_id])

            items = [
                {
                    'name': r[0],
                    'quantity': float(r[1]),
                    'unit_price': float(r[2]),
                    'total_price': float(r[3])
                }
                for r in cursor.fetchall()
            ]

        else:
            # Not in daily_sales — try historical sales table and sale_items
            cursor.execute("""
                SELECT 
                    s.id,
                    s.sale_number,
                    s.total_amount,
                    s.final_amount,
                    s.delivery_fee,
                    s.created_at,
                    s.customer_name,
                    s.customer_phone,
                    s.address_line1,
                    s.address_line2,
                    s.address_line3,
                    s.payment_method,
                    s.status
                FROM sales s
                WHERE s.id = ?
            """, [order_id])

            order_row = cursor.fetchone()
            if not order_row:
                return jsonify({'success': False, 'error': 'Order not found'})

            cursor.execute("""
                SELECT 
                    si.item_name,
                    si.quantity,
                    si.unit_price,
                    si.total_price
                FROM sale_items si
                WHERE si.sale_id = ?
            """, [order_id])

            items = [
                {
                    'name': r[0],
                    'quantity': float(r[1]),
                    'unit_price': float(r[2]),
                    'total_price': float(r[3])
                }
                for r in cursor.fetchall()
            ]

        # Combine address lines with spaces between non-empty parts
        address_parts = [part for part in [order_row[8], order_row[9], order_row[10]] if part]
        full_address = ' - '.join(address_parts) if address_parts else '-'

        # created_at may be a datetime or string; format if possible
        created_val = order_row[5]
        try:
            created_str = created_val.strftime('%Y-%m-%d %I:%M %p') if hasattr(created_val, 'strftime') else str(created_val)
        except Exception:
            created_str = str(created_val)

        order_data = {
            'id': order_row[0],
            'sale_number': order_row[1],
            'total_amount': float(order_row[2]) if order_row[2] is not None else 0,
            'final_amount': float(order_row[3]) if order_row[3] is not None else 0,
            'delivery_fee': float(order_row[4]) if order_row[4] else 0,
            'created_at': created_str,
            'customer_name': order_row[6] or '-',
            'customer_phone': order_row[7] or '-',
            'address': full_address,
            'address_line1': order_row[8] or '-',
            'address_line2': order_row[9] or '-',
            'address_line3': order_row[10] or '-',
            'payment_method': order_row[11] or 'نقدي',
            'status': order_row[12] or 'pending'
        }

        return jsonify({
            'success': True,
            'order': order_data,
            'items': items
        })

    except Exception as e:
        print(f"Error getting order details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route('/get_delivery_workers_dlev')
@login_required
def get_delivery_workers_dlev():
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, phone, status
            FROM delivery_workers
            WHERE status = 'active'
            ORDER BY name
        """)
        
        workers = [
            {
                'id': row[0],
                'name': row[1],
                'phone': row[2],
                'status': row[3]
            }
            for row in cursor.fetchall()
        ]

        return jsonify({
            'success': True,
            'workers': workers
        })

    except Exception as e:
        print(f"Error fetching delivery workers: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get order details
        cursor.execute("""
            SELECT 
                ds.id,
                ds.sale_number,
                ds.total_amount,
                ds.discount_amount,
                ds.delivery_fee,
                ds.final_amount,
                ds.customer_name,
                ds.customer_phone,
                ds.address_line1,
                ds.address_line2,
                ds.address_line3,
                ds.created_at,
                ds.payment_method,
                ds.status
            FROM daily_sales ds
            WHERE ds.id = ?
        """, [order_id])
        
        order = cursor.fetchone()
        if not order:
            return jsonify({'success': False, 'error': 'Order not found'})

        # Get order items
        cursor.execute("""
            SELECT 
                dsi.item_name,
                dsi.quantity,
                dsi.unit_price,
                dsi.total_price
            FROM daily_sale_items dsi
            WHERE dsi.sale_id = ?
        """, [order_id])
        
        items = []
        for row in cursor.fetchall():
            items.append({
                'name': row[0],
                'quantity': float(row[1]),
                'unit_price': float(row[2]),
                'total_price': float(row[3])
            })

        order_data = {
            'id': order[0],
            'sale_number': order[1],
            'total_amount': float(order[2]),
            'discount_amount': float(order[3]) if order[3] else 0,
            'delivery_fee': float(order[4]) if order[4] else 0,
            'final_amount': float(order[5]),
            'customer_name': order[6],
            'customer_phone': order[7],
            'address': f"{order[8] or ''} {order[9] or ''} {order[10] or ''}".strip(),
            'created_at': order[11].strftime('%Y-%m-%d %H:%M:%S'),
            'payment_method': order[12],
            'status': order[13]
        }

        return jsonify({
            'success': True,
            'order': order_data,
            'items': items
        })

    except Exception as e:
        print(f"Error getting order details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/assign_delivery_worker', methods=['POST'])
@login_required
def assign_delivery_worker():
    try:
        data = request.get_json()
        delivery_worker_id = data.get('delivery_worker_id')
        order_ids = data.get('order_ids')

        if not delivery_worker_id or not order_ids:
            return jsonify({
                'success': False,
                'error': 'يجب تحديد عامل التوصيل والطلبات'
            }), 400

        conn = get_db()
        cursor = conn.cursor()

        # Get delivery worker name
        cursor.execute("""
            SELECT name FROM delivery_workers 
            WHERE id = ? AND status = 'active'
        """, [delivery_worker_id])
        
        worker = cursor.fetchone()
        if not worker:
            return jsonify({
                'success': False,
                'error': 'عامل التوصيل غير موجود أو غير نشط'
            }), 404

        worker_name = worker[0]

        # Start transaction
        try:
            # Update daily_sales
            for order_id in order_ids:
                cursor.execute("""
                    UPDATE daily_sales 
                    SET delivery_worker_id = ?,
                        delivery_worker_name = ?,
                        status = 'assigned'
                    WHERE id = ? 
                    AND (status = 'pending' OR status = 'assigned')
                """, [delivery_worker_id, worker_name, order_id])

                # Get the sale_number and shift_id to find corresponding record in sales table
                cursor.execute("""
                    SELECT sale_number, shift_id 
                    FROM daily_sales 
                    WHERE id = ?
                """, [order_id])
                
                sale_info = cursor.fetchone()
                if sale_info:
                    # Update corresponding record in sales table
                    cursor.execute("""
                        UPDATE sales 
                        SET delivery_worker_id = ?,
                            delivery_worker_name = ?,
                            status = 'assigned'
                        WHERE sale_number = ? 
                        AND shift_id = ?
                        AND (status = 'pending' OR status = 'assigned')
                    """, [delivery_worker_id, worker_name, sale_info[0], sale_info[1]])

            conn.commit()
            return jsonify({
                'success': True,
                'message': 'تم تعيين عامل التوصيل بنجاح',
                'worker_name': worker_name
            })

        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e

    except Exception as e:
        print(f"Error assigning delivery worker: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ أثناء تعيين عامل التوصيل'
        }), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/mark_orders_as_done', methods=['POST'])
@login_required
def mark_orders_as_done():
    try:
        data = request.get_json()
        order_ids = data.get('order_ids', [])

        if not order_ids:
            return jsonify({
                'success': False,
                'error': 'لم يتم تحديد أي طلبات'
            }), 400

        conn = get_db()
        cursor = conn.cursor()

        # Start transaction
        try:
            # Update orders status in daily_sales
            for order_id in order_ids:
                cursor.execute("""
                    UPDATE daily_sales 
                    SET status = 'done'
                    WHERE id = ? AND status = 'assigned'
                """, [order_id])

                # Get sale_number and shift_id to find corresponding record in sales table
                cursor.execute("""
                    SELECT sale_number, shift_id 
                    FROM daily_sales 
                    WHERE id = ?
                """, [order_id])
                
                sale_info = cursor.fetchone()
                if sale_info:
                    # Update corresponding record in sales table
                    cursor.execute("""
                        UPDATE sales 
                        SET status = 'done'
                        WHERE sale_number = ? 
                        AND shift_id = ?
                        AND status = 'assigned'
                    """, [sale_info[0], sale_info[1]])

            conn.commit()
            return jsonify({
                'success': True,
                'message': 'تم تحصيل المبالغ بنجاح'
            })

        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e

    except Exception as e:
        print(f"Error marking orders as done: {e}")
        if conn:
            conn.rollback()
        return jsonify({
            'success': False,
            'error': 'حدث خطأ أثناء تحصيل المبالغ'
        }), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@app.route('/get_completed_orders/<int:delivery_worker_id>')
@login_required
def get_completed_orders(delivery_worker_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                ds.id,
                ds.sale_number,
                ds.final_amount,
                ds.delivery_fee,
                ds.created_at,
                ds.customer_name,
                ds.customer_phone,
                ds.address_line1,
                ds.address_line2,
                ds.address_line3,
                ds.status
            FROM daily_sales ds
            WHERE ds.delivery_worker_id = ?
            AND ds.status = 'done'
            ORDER BY ds.created_at DESC
        """, [delivery_worker_id])
        
        orders = []
        for row in cursor.fetchall():
            # Combine address parts
            addr_parts = [row[7], row[8], row[9]]
            full_address = ' - '.join([p for p in addr_parts if p]) if any(addr_parts) else '-'
            orders.append({
                'id': row[0],
                'sale_number': row[1],
                'final_amount': float(row[2]),
                'delivery_fee': float(row[3]),
                'created_at': row[4].strftime('%Y-%m-%d %I:%M %p'),
                'customer_name': row[5] or '-',
                'customer_phone': row[6] or '-',
                'address': full_address,
                'status': row[10]
            })

        return jsonify({
            'success': True,
            'orders': orders
        })

    except Exception as e:
        print(f"Error fetching completed orders: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@app.route('/pay_delivery_fees', methods=['POST'])
@login_required
def pay_delivery_fees():
    try:
        data = request.get_json()
        delivery_worker_id = data.get('delivery_worker_id')
        amount = data.get('amount')
        order_ids = data.get('order_ids')

        if not all([delivery_worker_id, amount, order_ids]):
            return jsonify({'success': False, 'error': 'البيانات غير مكتملة'}), 400

        # Validate amount
        try:
            amount = float(amount)
            if amount <= 0:
                return jsonify({'success': False, 'error': 'المبلغ يجب أن يكون رقمًا موجبًا'}), 400
        except ValueError:
            return jsonify({'success': False, 'error': 'المبلغ غير صالح'}), 400

        conn = get_db()
        cursor = conn.cursor()

        try:
            conn.autocommit = True  # Ensure transaction works

            # Get active shift
            cursor.execute("""
                SELECT id FROM shifts 
                WHERE status = 'active' 
                ORDER BY start_time DESC
            """)
            shift = cursor.fetchone()

            if not shift:
                return jsonify({'success': False, 'error': 'لا يوجد وردية نشطة'}), 400

            shift_id = shift[0]

            # Get delivery worker name
            cursor.execute("SELECT name FROM delivery_workers WHERE id = ?", [delivery_worker_id])
            worker = cursor.fetchone()
            if not worker:
                return jsonify({'success': False, 'error': 'عامل التوصيل غير موجود'}), 404

            worker_name = worker[0]

            # Determine current active shift (prefer status='active'). If none, fallback to latest shift.
            cursor.execute("SELECT id, start_time FROM shifts WHERE status = 'active' ORDER BY start_time DESC")
            current_shift = cursor.fetchone()
            if current_shift:
                current_shift_id = current_shift[0]
                current_shift_start = current_shift[1]
            else:
                # fallback to the most recent shift regardless of status
                cursor.execute("SELECT TOP 1 id, start_time FROM shifts ORDER BY start_time DESC")
                latest = cursor.fetchone()
                current_shift_id = latest[0] if latest else None
                current_shift_start = latest[1] if latest else None

            # Always record the expense under the current (active/latest) shift if available
            recorded_shift_id = current_shift_id if current_shift_id is not None else shift_id
            # Get original shift start time and cashier_name for shift_date and label
            cursor.execute("SELECT start_time, cashier_name FROM shifts WHERE id = ?", [shift_id])
            orig_shift = cursor.fetchone()
            orig_shift_start = orig_shift[0] if orig_shift else None
            orig_cashier = orig_shift[1] if orig_shift and len(orig_shift) > 1 else None
            orig_shift_label = f"وردية {shift_id} - {orig_cashier}" if orig_cashier else f"وردية {shift_id}"

            # Insert expense record with shift_date (if available)
            try:
                cursor.execute("""
                    INSERT INTO expenses (shift_id, shift_date, amount, description)
                    VALUES (?, ?, ?, ?)
                """, [recorded_shift_id, orig_shift_start, amount, f'دفع مستحقات مندوب التوصيل - {worker_name} ({orig_shift_label})'])
            except Exception:
                # Fallback if DB doesn't have shift_date column (backwards compatibility)
                cursor.execute("""
                    INSERT INTO expenses (shift_id, amount, description)
                    VALUES (?, ?, ?)
                """, [recorded_shift_id, amount, f'دفع مستحقات مندوب التوصيل - {worker_name} ({orig_shift_label})'])

            # Update delivery worker status
            cursor.execute("""
                UPDATE delivery_workers
                SET status = 'inactive'
                WHERE id = ?
            """, [delivery_worker_id])

            # Update shift expenses safely for the shift where we recorded the expense
            cursor.execute("""
                UPDATE shifts
                SET expenses = COALESCE(expenses, 0) + ?
                WHERE id = ?
            """, [amount, recorded_shift_id])

            # Mark orders as paid
            for order_id in order_ids:
                cursor.execute("""
                    UPDATE daily_sales 
                    SET status = 'paid'
                    WHERE id = ?
                """, [order_id])

            conn.commit()
            return jsonify({'success': True, 'message': 'تم دفع المستحقات بنجاح'})

        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e

    except Exception as e:
        print(f"Error paying delivery fees: {e}")
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

#endregion






#region settings
@app.route('/settings')
@login_required
@permission_required('settings')
def settings():
    return render_template('settings.html')

@app.route('/get_printers')
def get_printers():
    printers = [printer[2] for printer in win32print.EnumPrinters(2)]
    return jsonify(printers)

@app.route('/get_settings')
@login_required
@permission_required('settings')
def get_settings():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM settings WHERE id = 1")
        row = cursor.fetchone()
        if row:
            return jsonify({
                'store_name': row.store_name,
                'store_phone': row.store_phone,
                'store_address': row.store_address,
                'receipt_footer': row.receipt_footer,
                'printer_name': row.printer_name
            })
        return jsonify({})
    finally:
        cursor.close()
        conn.close()

@app.route('/save_settings', methods=['POST'])
def save_settings():
    conn = get_db()
    cursor = conn.cursor()
    try:
        data = request.json
        # Check if settings exist
        cursor.execute("SELECT 1 FROM settings WHERE id = 1")
        exists = cursor.fetchone() is not None

        if exists:
            # Update existing settings
            cursor.execute("""
                UPDATE settings
                SET store_name = ?, 
                    store_phone = ?, 
                    store_address = ?,
                    receipt_footer = ?, 
                    printer_name = ?
                WHERE id = 1
            """, (
                data['store_name'], 
                data['store_phone'], 
                data['store_address'],
                data['receipt_footer'], 
                data['printer_name']
            ))
        else:
            # Insert new settings
            cursor.execute("""
                INSERT INTO settings (
                    store_name, 
                    store_phone, 
                    store_address,
                    receipt_footer, 
                    printer_name
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                data['store_name'], 
                data['store_phone'], 
                data['store_address'],
                data['receipt_footer'], 
                data['printer_name']
            ))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error saving settings: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/test_print', methods=['POST'])
def test_print():
    try:
        data = request.json
        printer_name = data.get('printer')
        
        if not printer_name:
            return jsonify({'success': False, 'error': 'لم يتم اختيار طابعة'})

        hprinter = win32print.OpenPrinter(printer_name)
        printer_info = win32print.GetPrinter(hprinter, 2)
        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(printer_name)
        dc.StartDoc('Test Print')
        dc.StartPage()

        font = win32ui.CreateFont({
            'name': 'Arial',
            'height': 40,
            'weight': 400
        })
        dc.SelectObject(font)
        
        dc.TextOut(100, 100, 'Test Print - اختبار الطباعة')
        dc.TextOut(100, 150, f'Printer: {printer_name}')
        dc.TextOut(100, 200, 'Date: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        dc.EndPage()
        dc.EndDoc()
        dc.DeleteDC()
        win32print.ClosePrinter(hprinter)

        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Print error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/print_barcodes', methods=['POST'])
@login_required
def print_barcodes():
    try:
        data = request.json
        printer_name = data.get('printer')
        barcodes = data.get('barcodes', [])
        
        if not printer_name:
            return jsonify({'success': False, 'error': 'لم يتم اختيار طابعة'})
        
        if not barcodes:
            return jsonify({'success': False, 'error': 'لا توجد باركودات للطباعة'})
        
        hprinter = win32print.OpenPrinter(printer_name)
        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(printer_name)
        dc.StartDoc('Barcode Print')
        
        # Dimensions: 40mm width, 25mm height, 2mm left margin using device DPI
        dpi_x = dc.GetDeviceCaps(LOGPIXELSX)
        dpi_y = dc.GetDeviceCaps(LOGPIXELSY)
        def mm_to_px(mm, dpi):
            try:
                return int(round((mm / 25.4) * float(dpi)))
            except Exception:
                # Fallback to 96 DPI if device caps not available
                return int(round((mm / 25.4) * 96.0))

        left_margin = mm_to_px(2, dpi_x)
        label_width = mm_to_px(40, dpi_x)
        label_height = mm_to_px(25, dpi_y)
        # Padding and layout (in mm)
        pad_side_px = mm_to_px(1, dpi_x)
        pad_top_px = mm_to_px(1, dpi_y)
        pad_bottom_px = mm_to_px(1, dpi_y)
        gap_px = mm_to_px(1, dpi_y)  # gap between text and barcode
        # Allocate a text block at the top that spans the full label width
        text_block_h_px = mm_to_px(7, dpi_y)  # ~7mm for up to 2 lines
        
        for barcode_data in barcodes:
            dc.StartPage()
            
            barcode_text = barcode_data.get('barcode', '')
            name = barcode_data.get('name', '')
            price = barcode_data.get('price', '')
            
            # 1) Draw text block at top spanning full label width
            try:
                # Create font for text (same as receipts)
                font_height_px = max(20, mm_to_px(3, dpi_y))
                text_font = win32ui.CreateFont({
                    'name': 'Arial',
                    'height': font_height_px,
                    'weight': 400
                })
                dc.SelectObject(text_font)
                dc.SetBkMode(TRANSPARENT)
                
                # Print name on first line (right-aligned for Arabic)
                name_str = '' if name is None else str(name)
                price_str = '' if price is None else str(price)
                
                y_text = int(pad_top_px)
                if name_str:
                    text_width = dc.GetTextExtent(name_str)[0]
                    x_text = int(left_margin + label_width - text_width)
                    dc.TextOut(x_text, y_text, name_str)
                    y_text += font_height_px + 5
                
                # Print price on second line (right-aligned)
                if price_str:
                    text_width = dc.GetTextExtent(price_str)[0]
                    x_text = int(left_margin + label_width - text_width)
                    dc.TextOut(x_text, y_text, price_str)
            except Exception as e:
                print(f"Text drawing failed: {e}")

            # 2) Draw barcode graphic below the text block, within remaining height
            if BARCODE_AVAILABLE and barcode_text:
                try:
                    from barcode import Code128
                    code128 = Code128(barcode_text, writer=ImageWriter())
                    barcode_image = code128.render(writer_options={
                        'write_text': False,
                        'quiet_zone': 1
                    })

                    # Available area for the barcode graphic
                    avail_top = int(pad_top_px + text_block_h_px + gap_px)
                    avail_height = int(label_height - (pad_top_px + text_block_h_px + gap_px + pad_bottom_px))
                    avail_width = int(max(10, label_width - pad_side_px * 2))
                    avail_height = max(10, avail_height)

                    # Preserve aspect ratio to fit within available area
                    scale = min(avail_width / float(barcode_image.width),
                                avail_height / float(barcode_image.height))
                    target_w = max(1, int(barcode_image.width * scale))
                    target_h = max(1, int(barcode_image.height * scale))
                    resized = barcode_image.resize((target_w, target_h), Image.LANCZOS).convert('RGB')

                    # Center horizontally within the label width
                    x1 = int(left_margin + (label_width - target_w) / 2)
                    y1 = int(avail_top + (avail_height - target_h) / 2)
                    x2 = int(x1 + target_w)
                    y2 = int(y1 + target_h)
                    hdc = dc.GetHandleOutput()
                    ImageWin.Dib(resized).draw(hdc, (x1, y1, x2, y2))
                except Exception as e:
                    print(f"Barcode generation/printing failed: {e}")
                    # Fallback to text-only barcode representation
                    try:
                        dc.TextOut(int(left_margin), int(pad_top_px + text_block_h_px + gap_px), f"*{barcode_text}*")
                    except Exception:
                        pass
            else:
                # Fallback to text-only barcode representation
                try:
                    dc.TextOut(int(left_margin), int(pad_top_px + text_block_h_px + gap_px), f"*{barcode_text}*")
                except Exception:
                    pass
            
            dc.EndPage()
        
        dc.EndDoc()
        dc.DeleteDC()
        win32print.ClosePrinter(hprinter)
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Barcode print error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/get_users')
def get_users():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, username, password, permissions 
            FROM users 
            ORDER BY username
        """)
        users = cursor.fetchall()
        return jsonify([{
            'id': user.id,
            'username': user.username,
            'password': user.password,
            'permissions': user.permissions.split(',')
        } for user in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()



@app.route('/add_user', methods=['POST'])
def add_user():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.get_json()
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO users (username, password, permissions)
            VALUES (?, ?, ?)
        """, [data['username'], data['password'], data['permissions']])
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/delete_user/<int:user_id>', methods=['DELETE'])
@login_required
@permission_required('settings')
def delete_user(user_id):
    if user_id == 1:  # Prevent deleting admin user
        return jsonify({'error': 'لا يمكن حذف المستخدم الرئيسي'}), 400
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", [user_id])
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_user/<int:user_id>')
@login_required
@permission_required('settings')
def get_user(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, password, permissions 
            FROM users 
            WHERE id = ?
        """, [user_id])
        user = cursor.fetchone()
        if user:
            return jsonify({
                'id': user[0],
                'username': user[1],
                'password': user[2],
                'permissions': user[3]
            })
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        print(f"Error getting user: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/update_user/<int:user_id>', methods=['PUT'])
@login_required
@permission_required('settings')
def update_user(user_id):
    if user_id == 1:  # Protect admin user
        return jsonify({'error': 'لا يمكن تعديل المستخدم الرئيسي'}), 400
        
    try:
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET username = ?, password = ?, permissions = ? 
            WHERE id = ?
        """, [data['username'], data['password'], data['permissions'], user_id])
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error updating user: {e}")
        return jsonify({'error': str(e)}), 500




@app.context_processor
def utility_processor():
    def has_permission(permission):
        return permission in session.get('permissions', [])
    return dict(has_permission=has_permission)




# Add in the settings region

# Update the get_delivery_workers route

@app.route('/get_delivery_workers')
@login_required
@permission_required('settings')
def get_delivery_workers():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, phone, status
            FROM delivery_workers
            ORDER BY 
                CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                name
        """)
        workers = [{
            'id': row[0],
            'name': row[1],
            'phone': row[2],
            'status': row[3]
        } for row in cursor.fetchall()]
        return jsonify(workers)
    except Exception as e:
        print(f"Error getting delivery workers: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/save_delivery_worker', methods=['POST'])
@login_required
@permission_required('settings')
def save_delivery_worker():
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO delivery_workers (name, phone)
            VALUES (?, ?)
        """, [data['name'], data['phone']])
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error saving delivery worker: {e}")
        return jsonify({'error': str(e)}), 500

# Update the update_delivery_worker route

@app.route('/update_delivery_worker/<int:worker_id>', methods=['PUT'])
@login_required
@permission_required('settings')
def update_delivery_worker(worker_id):
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        # If only status is being updated
        if 'status' in data and len(data) == 1:
            cursor.execute("""
                UPDATE delivery_workers
                SET status = ?, updated_at = GETDATE()
                WHERE id = ?
            """, [data['status'], worker_id])
        else:
            # Full update
            cursor.execute("""
                UPDATE delivery_workers
                SET name = ?, phone = ?, status = ?, updated_at = GETDATE()
                WHERE id = ?
            """, [data['name'], data['phone'], data.get('status', 'active'), worker_id])
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error updating delivery worker: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/delete_delivery_worker/<int:worker_id>', methods=['DELETE'])
@login_required
@permission_required('settings')
def delete_delivery_worker(worker_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM delivery_workers WHERE id = ?", [worker_id])
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting delivery worker: {e}")
        return jsonify({'error': str(e)}), 500
#endregion

#region Employees Management

@app.route('/employees')
@login_required
@permission_required('employees')
def employees_page():
    """Employees management page"""
    return render_template('employees.html')

@app.route('/get_employees')
@login_required
@permission_required('employees')
def get_employees():
    """Get all employees"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, phone, job_title, is_active, created_at
            FROM employees
            ORDER BY name
        """)
        
        employees = []
        for row in cursor.fetchall():
            employees.append({
                'id': row[0],
                'name': row[1],
                'phone': row[2],
                'job_title': row[3],
                'is_active': bool(row[4]),
                'created_at': row[5].strftime('%Y-%m-%d') if row[5] else None
            })
        
        return jsonify(employees)
    except Exception as e:
        print(f"Error getting employees: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/add_employee', methods=['POST'])
@login_required
@permission_required('employees')
def add_employee():
    """Add new employee"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO employees (name, phone, job_title, is_active)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, 1)
        """, [data['name'], data.get('phone', ''), data.get('job_title', '')])
        
        employee_id = cursor.fetchone()[0]
        conn.commit()
        
        # Log activity
        log_activity('employee', f'Employee added: {data["name"]}', 'employees', employee_id)
        
        return jsonify({'success': True, 'id': employee_id})
    except Exception as e:
        print(f"Error adding employee: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/update_employee/<int:employee_id>', methods=['PUT'])
@login_required
@permission_required('employees')
def update_employee(employee_id):
    """Update employee"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE employees
            SET name = ?, phone = ?, job_title = ?, updated_at = GETDATE()
            WHERE id = ?
        """, [data['name'], data.get('phone', ''), data.get('job_title', ''), employee_id])
        
        conn.commit()
        
        # Log activity
        log_activity('employee', f'Employee updated: {data["name"]}', 'employees', employee_id)
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error updating employee: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/toggle_employee_status/<int:employee_id>', methods=['PUT'])
@login_required
@permission_required('employees')
def toggle_employee_status(employee_id):
    """Activate/Deactivate employee"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE employees
            SET is_active = ?, updated_at = GETDATE()
            WHERE id = ?
        """, [data['is_active'], employee_id])
        
        conn.commit()
        
        status = 'activated' if data['is_active'] else 'deactivated'
        log_activity('employee', f'Employee {status}', 'employees', employee_id)
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error toggling employee status: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/add_disbursement', methods=['POST'])
@login_required
@permission_required('employees')
def add_disbursement():
    """Add employee disbursement (صرف)"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        user_id = session.get('user_id')
        username = session.get('username')
        
        # Get نقدي cash box
        cursor.execute("SELECT id FROM cash_boxes WHERE name = N'نقدي' AND is_active = 1")
        cash_box_result = cursor.fetchone()
        if not cash_box_result:
            return jsonify({'error': 'نقدي cash box not found'}), 404
        
        cash_box_id = cash_box_result[0]
        
        # Insert disbursement
        cursor.execute("""
            INSERT INTO employee_disbursements 
            (employee_id, amount, notes, cash_box_id, given_by_user_id, given_by_username)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?)
        """, [data['employee_id'], data['amount'], data.get('notes', ''), 
              cash_box_id, user_id, username])
        
        disbursement_id = cursor.fetchone()[0]
        
        # Add to cash_box_transfers (money going OUT from نقدي)
        cursor.execute("""
            INSERT INTO cash_box_transfers 
            (from_cash_box_id, to_cash_box_id, amount, notes, user_id)
            VALUES (?, NULL, ?, ?, ?)
        """, [cash_box_id, data['amount'], 
              f"صرف للموظف: {data.get('employee_name', 'موظف')} - {data.get('notes', '')}", 
              user_id])
        
        conn.commit()
        
        # Log activity
        log_activity('disbursement', 
                    f'Disbursement added: {data["amount"]} to employee {data.get("employee_name", "")}', 
                    'employee_disbursements', disbursement_id)
        
        return jsonify({'success': True, 'id': disbursement_id})
    except Exception as e:
        print(f"Error adding disbursement: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/get_disbursements')
@login_required
@permission_required('employees')
def get_disbursements():
    """Get employee disbursements with filtering"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        employee_id = request.args.get('employee_id', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        query = """
            SELECT 
                ed.id,
                ed.employee_id,
                e.name as employee_name,
                ed.amount,
                ed.disbursement_date,
                ed.notes,
                ed.given_by_username
            FROM employee_disbursements ed
            JOIN employees e ON ed.employee_id = e.id
            WHERE 1=1
        """
        params = []
        
        if employee_id:
            query += " AND ed.employee_id = ?"
            params.append(employee_id)
        
        if start_date:
            query += " AND ed.disbursement_date >= ?"
            params.append(start_date + ' 00:00:00')
        
        if end_date:
            query += " AND ed.disbursement_date <= ?"
            params.append(end_date + ' 23:59:59')
        
        query += " ORDER BY ed.disbursement_date DESC"
        
        cursor.execute(query, params)
        
        disbursements = []
        for row in cursor.fetchall():
            disbursements.append({
                'id': row[0],
                'employee_id': row[1],
                'employee_name': row[2],
                'amount': float(row[3]),
                'disbursement_date': row[4].strftime('%Y-%m-%d %H:%M:%S') if row[4] else None,
                'notes': row[5],
                'given_by': row[6]
            })
        
        return jsonify(disbursements)
    except Exception as e:
        print(f"Error getting disbursements: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/get_employee_disbursement_summary')
@login_required
@permission_required('employees')
def get_employee_disbursement_summary():
    """Get summary of disbursements grouped by employee"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        query = """
            SELECT 
                e.id,
                e.name,
                e.phone,
                e.job_title,
                ISNULL(SUM(ed.amount), 0) as total_amount,
                COUNT(ed.id) as disbursement_count
            FROM employees e
            LEFT JOIN employee_disbursements ed ON e.id = ed.employee_id
        """
        params = []
        where_clauses = []
        
        if start_date:
            where_clauses.append("ed.disbursement_date >= ?")
            params.append(start_date + ' 00:00:00')
        
        if end_date:
            where_clauses.append("ed.disbursement_date <= ?")
            params.append(end_date + ' 23:59:59')
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        query += """
            GROUP BY e.id, e.name, e.phone, e.job_title
            ORDER BY e.name
        """
        
        cursor.execute(query, params)
        
        summary = []
        for row in cursor.fetchall():
            summary.append({
                'employee_id': row[0],
                'employee_name': row[1],
                'phone': row[2],
                'job_title': row[3],
                'total_amount': float(row[4]),
                'disbursement_count': int(row[5])
            })
        
        return jsonify(summary)
    except Exception as e:
        print(f"Error getting disbursement summary: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

#endregion

#region Activity Logs

@app.route('/activity_logs')
@login_required
@permission_required('settings')
def activity_logs():
    """Activity logs page - shows all user activities"""
    return render_template('activity_logs.html')

@app.route('/get_activity_logs')
@login_required
@permission_required('settings')
def get_activity_logs():
    """Get activity logs with filtering and pagination"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        user_id = request.args.get('user_id', '')
        action_type = request.args.get('action_type', '')
        table_name = request.args.get('table_name', '')
        
        print(f"Loading logs - page: {page}, start_date: {start_date}, end_date: {end_date}")
        
        # Build WHERE clause
        where_clauses = []
        params = []
        
        if start_date:
            where_clauses.append("CAST(created_at AS DATE) >= ?")
            params.append(start_date)
        
        if end_date:
            where_clauses.append("CAST(created_at AS DATE) <= ?")
            params.append(end_date)
        
        if user_id:
            where_clauses.append("user_id = ?")
            params.append(user_id)
        
        if action_type:
            where_clauses.append("action_type = ?")
            params.append(action_type)
        
        if table_name:
            where_clauses.append("table_name = ?")
            params.append(table_name)
        
        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        print(f"WHERE SQL: {where_sql}, Params: {params}")
        
        # Get total count
        cursor.execute(f"SELECT COUNT(*) FROM activity_logs {where_sql}", params)
        total_logs = cursor.fetchone()[0]
        total_pages = (total_logs + limit - 1) // limit if total_logs > 0 else 1
        
        print(f"Total logs found: {total_logs}")
        
        # Get logs for current page
        offset = (page - 1) * limit
        cursor.execute(f"""
            SELECT 
                id, user_id, username, action_type, table_name, 
                record_id, description, ip_address, created_at
            FROM activity_logs
            {where_sql}
            ORDER BY created_at DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, params + [offset, limit])
        
        logs = []
        for row in cursor.fetchall():
            log_entry = {
                'id': row[0],
                'user_id': row[1],
                'username': row[2],
                'action_type': row[3],
                'table_name': row[4],
                'record_id': row[5],
                'description': row[6],
                'ip_address': row[7],
                'created_at': row[8].strftime('%Y-%m-%d %H:%M:%S') if row[8] else None
            }
            logs.append(log_entry)
            print(f"Log entry: {log_entry}")
        
        print(f"Returning {len(logs)} logs")
        
        return jsonify({
            'success': True,
            'logs': logs,
            'total_logs': total_logs,
            'total_pages': total_pages,
            'current_page': page
        })
        
    except Exception as e:
        print(f"Error getting activity logs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/get_activity_stats')
@login_required
@permission_required('settings')
def get_activity_stats():
    """Get activity statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total logs
        cursor.execute("SELECT COUNT(*) FROM activity_logs")
        total_logs = cursor.fetchone()[0]
        
        # Today's logs
        cursor.execute("""
            SELECT COUNT(*) 
            FROM activity_logs 
            WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)
        """)
        today_logs = cursor.fetchone()[0]
        
        # Active users (users who performed actions in last 7 days)
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) 
            FROM activity_logs 
            WHERE created_at >= DATEADD(day, -7, GETDATE())
        """)
        active_users = cursor.fetchone()[0]
        
        return jsonify({
            'success': True,
            'total_logs': total_logs,
            'today_logs': today_logs,
            'active_users': active_users
        })
        
    except Exception as e:
        print(f"Error getting activity stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

#endregion

#region Cash Boxes Management

@app.route('/cash_boxes')
@login_required
@permission_required('settings')
def cash_boxes_page():
    return render_template('cash_boxes.html')

@app.route('/get_cash_boxes')
@login_required
def get_cash_boxes():
    """Get all cash boxes with their current balances"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, is_default, is_active, created_at
            FROM cash_boxes
            WHERE is_active = 1
            ORDER BY is_default DESC, name
        """)
        boxes = cursor.fetchall()
        
        result = []
        for box in boxes:
            box_id = box[0]
            
            # Calculate balance for this cash box (same logic as get_cash_box_summary)
            # 1. Get total from shift_cash_boxes (includes sales income)
            cursor.execute("""
                SELECT ISNULL(SUM(amount), 0)
                FROM shift_cash_boxes
                WHERE cash_box_id = ?
            """, [box_id])
            shift_amounts = float(cursor.fetchone()[0] or 0)
            
            # 2. Get only the returns from sale_returns table (NOT daily_sale_returns)
            cursor.execute("""
                SELECT ISNULL(SUM(sr.total_amount), 0)
                FROM sale_returns sr
                INNER JOIN sales s ON sr.sale_id = s.id
                WHERE s.cash_box_id = ? AND sr.status = 'completed'
            """, [box_id])
            sale_returns_total = float(cursor.fetchone()[0] or 0)
            
            # 3. Get transfers IN to this cash box (deposits and transfers from other boxes)
            cursor.execute("""
                SELECT ISNULL(SUM(amount), 0)
                FROM cash_box_transfers
                WHERE to_cash_box_id = ?
            """, [box_id])
            transfers_in = float(cursor.fetchone()[0] or 0)
            
            # 4. Get transfers OUT from this cash box (withdrawals and transfers to other boxes)
            cursor.execute("""
                SELECT ISNULL(SUM(amount), 0)
                FROM cash_box_transfers
                WHERE from_cash_box_id = ?
            """, [box_id])
            transfers_out = float(cursor.fetchone()[0] or 0)
            
            # Calculate total balance (same as cash boxes report page)
            # Balance = Shift amounts (includes sales) - Sale Returns + Transfers IN - Transfers OUT
            balance = shift_amounts - sale_returns_total + transfers_in - transfers_out
            
            result.append({
                'id': box[0],
                'name': box[1],
                'is_default': bool(box[2]),
                'is_active': bool(box[3]),
                'balance': balance,
                'created_at': box[4].strftime('%Y-%m-%d %H:%M:%S') if box[4] else None
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/get_all_cash_boxes')
@login_required
@permission_required('settings')
def get_all_cash_boxes():
    """Get all cash boxes (including inactive) - used by settings page"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, is_default, is_active, created_at
            FROM cash_boxes
            ORDER BY is_default DESC, name
        """)
        boxes = cursor.fetchall()
        return jsonify([{
            'id': box[0],
            'name': box[1],
            'is_default': bool(box[2]),
            'is_active': bool(box[3]),
            'created_at': box[4].strftime('%Y-%m-%d %H:%M:%S') if box[4] else None
        } for box in boxes])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/add_cash_box', methods=['POST'])
@login_required
@permission_required('settings')
def add_cash_box():
    """Add a new cash box"""
    try:
        data = request.json
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'success': False, 'error': 'اسم الصندوق مطلوب'})
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if name already exists
        cursor.execute("SELECT id FROM cash_boxes WHERE name = ?", [name])
        if cursor.fetchone():
            return jsonify({'success': False, 'error': 'هذا الصندوق موجود بالفعل'})
        
        cursor.execute("""
            INSERT INTO cash_boxes (name, is_default, is_active)
            VALUES (?, 0, 1)
        """, [name])
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if conn:
            conn.close()

@app.route('/delete_cash_box/<int:box_id>', methods=['DELETE'])
@login_required
@permission_required('settings')
def delete_cash_box(box_id):
    """Delete a cash box (only non-default ones)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if it's a default box
        cursor.execute("SELECT is_default FROM cash_boxes WHERE id = ?", [box_id])
        row = cursor.fetchone()
        
        if not row:
            return jsonify({'success': False, 'error': 'الصندوق غير موجود'})
        
        if row[0]:  # is_default
            return jsonify({'success': False, 'error': 'لا يمكن حذف الصناديق الافتراضية'})
        
        # Soft delete
        cursor.execute("UPDATE cash_boxes SET is_active = 0 WHERE id = ?", [box_id])
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if conn:
            conn.close()


@app.route('/set_cash_box_active', methods=['POST'])
@login_required
@permission_required('settings')
def set_cash_box_active():
    """Enable or disable a cash box (cannot disable defaults)"""
    try:
        data = request.json
        box_id = int(data.get('box_id'))
        active = bool(data.get('active'))

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT is_default FROM cash_boxes WHERE id = ?", [box_id])
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'الصندوق غير موجود'})

        is_default = bool(row[0])
        if is_default and not active:
            return jsonify({'success': False, 'error': 'لا يمكن إيقاف الصناديق الافتراضية'})

        cursor.execute("UPDATE cash_boxes SET is_active = ? WHERE id = ?", [1 if active else 0, box_id])
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if conn:
            conn.close()

@app.route('/get_cash_box_summary')
@login_required
def get_cash_box_summary():
    """Get summary of all cash boxes with their current balances calculated from shifts, sales, and transfers"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get all active cash boxes
        cursor.execute("""
            SELECT 
                cb.id,
                cb.name,
                cb.is_default
            FROM cash_boxes cb
            WHERE cb.is_active = 1
            ORDER BY cb.is_default DESC, cb.name
        """)
        
        boxes = cursor.fetchall()
        
        # Calculate balance for each cash box
        cash_boxes = []
        for box in boxes:
            box_id = box[0]
            
            # 1. Get total from shift_cash_boxes (the recorded amounts for this cash box in shifts)
            # This already includes the money from sales
            cursor.execute("""
                SELECT ISNULL(SUM(amount), 0)
                FROM shift_cash_boxes
                WHERE cash_box_id = ?
            """, [box_id])
            shift_amounts = float(cursor.fetchone()[0] or 0)
            
            # 2. Get only the returns from sale_returns table (NOT daily_sale_returns)
            cursor.execute("""
                SELECT ISNULL(SUM(sr.total_amount), 0)
                FROM sale_returns sr
                INNER JOIN sales s ON sr.sale_id = s.id
                WHERE s.cash_box_id = ? AND sr.status = 'completed'
            """, [box_id])
            sale_returns_total = float(cursor.fetchone()[0] or 0)
            
            # 3. Get transfers IN to this cash box (deposits and transfers from other boxes)
            cursor.execute("""
                SELECT ISNULL(SUM(amount), 0)
                FROM cash_box_transfers
                WHERE to_cash_box_id = ?
            """, [box_id])
            transfers_in = float(cursor.fetchone()[0] or 0)
            
            # 4. Get transfers OUT from this cash box (withdrawals and transfers to other boxes)
            cursor.execute("""
                SELECT ISNULL(SUM(amount), 0)
                FROM cash_box_transfers
                WHERE from_cash_box_id = ?
            """, [box_id])
            transfers_out = float(cursor.fetchone()[0] or 0)
            
            # Calculate total balance
            # Balance = Shift amounts (includes sales) - Sale Returns only + Transfers IN - Transfers OUT
            balance = shift_amounts - sale_returns_total + transfers_in - transfers_out
            
            cash_boxes.append({
                'id': box[0],
                'name': box[1],
                'is_default': bool(box[2]),
                'amount': balance
            })
        
        return jsonify({'success': True, 'cash_boxes': cash_boxes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/transfer_cash', methods=['POST'])
@login_required
def transfer_cash():
    """Transfer money between cash boxes"""
    try:
        data = request.json
        from_box_id = data.get('from_cash_box_id')
        to_box_id = data.get('to_cash_box_id')
        amount = data.get('amount')
        notes = data.get('notes', '')
        
        if not all([from_box_id, to_box_id, amount]):
            return jsonify({'success': False, 'error': 'جميع الحقول مطلوبة'})
        
        if from_box_id == to_box_id:
            return jsonify({'success': False, 'error': 'لا يمكن التحويل إلى نفس الصندوق'})
        
        amount = float(amount)
        if amount <= 0:
            return jsonify({'success': False, 'error': 'المبلغ يجب أن يكون أكبر من صفر'})
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Get current active shift
        cursor.execute("SELECT id FROM shifts WHERE status = 'active'")
        active_shift = cursor.fetchone()
        shift_id = active_shift[0] if active_shift else None
        
        # Record the transfer
        cursor.execute("""
            INSERT INTO cash_box_transfers 
            (from_cash_box_id, to_cash_box_id, amount, shift_id, notes, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [from_box_id, to_box_id, amount, shift_id, notes, session.get('user_id')])
        
        # Note: We don't update shift_cash_boxes here because cash_box_transfers
        # already tracks all movements and is used in balance calculation
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if conn:
            conn.close()

@app.route('/get_cash_box_transfers')
@login_required
def get_cash_box_transfers():
    """Get transfer history with filtering"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        cash_box_id = request.args.get('cash_box_id')
        
        query = """
            SELECT 
                t.id,
                t.amount,
                t.transfer_date,
                t.notes,
                t.from_cash_box_id,
                t.to_cash_box_id,
                cb1.name as from_box_name,
                cb2.name as to_box_name,
                u.username,
                s.id as shift_id
            FROM cash_box_transfers t
            LEFT JOIN cash_boxes cb1 ON t.from_cash_box_id = cb1.id
            LEFT JOIN cash_boxes cb2 ON t.to_cash_box_id = cb2.id
            LEFT JOIN users u ON t.user_id = u.id
            LEFT JOIN shifts s ON t.shift_id = s.id
            WHERE 1=1
        """
        params = []
        
        if start_date:
            query += " AND t.transfer_date >= ?"
            params.append(f"{start_date} 00:00:00")
        
        if end_date:
            query += " AND t.transfer_date <= ?"
            params.append(f"{end_date} 23:59:59")
        
        if cash_box_id:
            query += " AND (t.from_cash_box_id = ? OR t.to_cash_box_id = ?)"
            params.extend([cash_box_id, cash_box_id])
        
        query += " ORDER BY t.transfer_date DESC"
        
        cursor.execute(query, params)
        
        transfers = cursor.fetchall()
        result = []
        for t in transfers:
            # Determine transaction type
            if t[4] is None:  # from_cash_box_id is NULL
                transaction_type = 'deposit'
            elif t[5] is None:  # to_cash_box_id is NULL
                transaction_type = 'withdraw'
            else:
                transaction_type = 'transfer'
            
            result.append({
                'id': t[0],
                'amount': float(t[1]),
                'transfer_date': t[2].strftime('%Y-%m-%d %H:%M:%S') if t[2] else None,
                'notes': t[3],
                'from_cash_box_id': t[4],
                'to_cash_box_id': t[5],
                'from_cash_box_name': t[6],
                'to_cash_box_name': t[7],
                'user_name': t[8],
                'shift_id': t[9],
                'transaction_type': transaction_type
            })
        
        return jsonify({'success': True, 'transfers': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/cash_boxes_report')
@login_required
@permission_required('cash_boxes_report')
def cash_boxes_report():
    return render_template('cash_boxes_report.html')

@app.route('/deposit_cash', methods=['POST'])
@login_required
@permission_required('cash_boxes_report')
def deposit_cash():
    try:
        data = request.get_json()
        cash_box_id = data.get('cash_box_id')
        amount = float(data.get('amount', 0))
        notes = data.get('notes', '')
        
        if not cash_box_id or amount <= 0:
            return jsonify({'success': False, 'error': 'بيانات غير صحيحة'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Get current active shift
        cursor.execute("SELECT id FROM shifts WHERE status = 'active'")
        shift_row = cursor.fetchone()
        shift_id = shift_row[0] if shift_row else None
        
        # Insert deposit as a transfer (from null to cash box)
        cursor.execute("""
            INSERT INTO cash_box_transfers 
            (from_cash_box_id, to_cash_box_id, amount, shift_id, notes, user_id)
            VALUES (NULL, ?, ?, ?, ?, ?)
        """, [cash_box_id, amount, shift_id, notes, session.get('user_id')])
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/withdraw_cash', methods=['POST'])
@login_required
@permission_required('cash_boxes_report')
def withdraw_cash():
    try:
        data = request.get_json()
        cash_box_id = data.get('cash_box_id')
        amount = float(data.get('amount', 0))
        notes = data.get('notes', '')
        
        if not cash_box_id or amount <= 0:
            return jsonify({'success': False, 'error': 'بيانات غير صحيحة'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Get current active shift
        cursor.execute("SELECT id FROM shifts WHERE status = 'active'")
        shift_row = cursor.fetchone()
        shift_id = shift_row[0] if shift_row else None
        
        # Insert withdraw as a transfer (from cash box to null)
        cursor.execute("""
            INSERT INTO cash_box_transfers 
            (from_cash_box_id, to_cash_box_id, amount, shift_id, notes, user_id)
            VALUES (?, NULL, ?, ?, ?, ?)
        """, [cash_box_id, amount, shift_id, notes, session.get('user_id')])
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

#endregion











#region Reciepts(بونات)

@app.route('/sales')
@login_required
@permission_required('sales')
def sales():
    conn = get_db()
    cursor = conn.cursor()
    sales_dict = {}
    
    try:
        # Get current active shift
        cursor.execute("""
            SELECT TOP 1 id FROM shifts 
            WHERE end_time IS NULL 
            ORDER BY start_time DESC
        """)
        shift = cursor.fetchone()
        
        if not shift:
            return render_template('sales.html', sales_list=[])

        # Get daily sales with return status and delivery information
        cursor.execute("""
            SELECT s.id, s.sale_number, s.total_amount, s.discount_amount, 
                   s.delivery_fee, s.final_amount, s.payment_method, s.created_at,
                   s.customer_name, s.customer_phone, 
                   s.address_line1, s.address_line2, s.address_line3,
                   s.delivery_worker_name, s.status,
                   CASE 
                       WHEN EXISTS (
                           SELECT 1 FROM daily_sale_returns sr 
                           WHERE sr.sale_id = s.id
                       ) THEN 
                           CASE 
                               -- Check if all items with their full quantities were returned
                               WHEN NOT EXISTS (
                                   SELECT 1 FROM daily_sale_items si 
                                   WHERE si.sale_id = s.id 
                                   AND si.quantity > ISNULL((
                                       SELECT SUM(ri.quantity) 
                                       FROM daily_return_items ri 
                                       JOIN daily_sale_returns sr ON ri.return_id = sr.id 
                                       WHERE sr.sale_id = s.id AND ri.item_id = si.item_id
                                   ), 0)
                               ) THEN 'full'
                               ELSE 'partial'
                           END
                       ELSE NULL
                   END as return_status
            FROM daily_sales s
            WHERE s.shift_id = ?
            ORDER BY s.created_at DESC
        """, [shift.id])
        
        sales_rows = cursor.fetchall()
        
        for sale in sales_rows:
            # Get sale items with return status
            cursor.execute("""
                SELECT 
                    si.id,
                    si.item_name,
                    si.quantity,
                    si.unit_price,
                    si.total_price,
                    CASE 
                        WHEN si.quantity <= ISNULL(
                            (SELECT SUM(ri.quantity) 
                             FROM daily_return_items ri 
                             JOIN daily_sale_returns sr ON ri.return_id = sr.id 
                             WHERE sr.sale_id = ? AND ri.item_id = si.item_id), 
                            0
                        ) THEN 1 
                        ELSE 0 
                    END as is_returned,
                    ISNULL(
                        (SELECT SUM(ri.quantity) 
                         FROM daily_return_items ri 
                         JOIN daily_sale_returns sr ON ri.return_id = sr.id 
                         WHERE sr.sale_id = ? AND ri.item_id = si.item_id), 
                        0
                    ) as returned_quantity
                FROM daily_sale_items si
                WHERE si.sale_id = ?
            """, [sale.id, sale.id, sale.id])
            
            sale_items = cursor.fetchall()
            
            # Combine address lines for display
            address_parts = [part for part in [sale[10], sale[11], sale[12]] if part]
            full_address = ' - '.join(address_parts) if address_parts else None
            
            sales_dict[sale.id] = {
                'id': sale.id,
                'sale_number': sale.sale_number,
                'total_amount': float(sale.total_amount),
                'discount_amount': float(sale.discount_amount or 0),
                'delivery_fee': float(sale.delivery_fee or 0),
                'final_amount': float(sale.final_amount),
                'payment_method': sale.payment_method,
                'created_at': sale.created_at,
                'customer_name': sale[8],
                'customer_phone': sale[9],
                'address': full_address,
                'delivery_worker_name': sale[13],
                'status': sale[14],
                'return_status': sale.return_status,
                'sale_items': [{
                    'id': item.id,
                    'item_name': item.item_name,
                    'quantity': float(item.quantity),
                    'unit_price': float(item.unit_price),
                    'total_price': float(item.total_price),
                    'is_returned': bool(item.is_returned),
                    'returned_quantity': float(item.returned_quantity)
                } for item in sale_items]
            }
        
        return render_template('sales.html', sales_list=list(sales_dict.values()))
        
    finally:
        cursor.close()
        conn.close()
@app.route('/get_sale_items/<int:sale_id>')
@login_required
def get_sale_items(sale_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, item_name, quantity, unit_price, total_price
            FROM daily_sale_items
            WHERE sale_id = ?
        """, [sale_id])
        
        items = [dict(zip(['id', 'item_name', 'quantity', 'unit_price', 'total_price'], row))
                for row in cursor.fetchall()]
                
        return jsonify({'items': items})
    except Exception as e:
        print(f"Error getting sale items: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/process_return', methods=['POST'])
@login_required
def process_return():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        print(f"Received return data: {data}")
        
        required_fields = ['sale_id', 'reason', 'type']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Get current active shift
        cursor.execute("""
            SELECT TOP 1 id FROM shifts 
            WHERE status = 'active' 
            ORDER BY start_time DESC
        """)
        shift = cursor.fetchone()
        if not shift:
            raise Exception("No active shift found")

        # Get both daily and regular sale IDs
        cursor.execute("""
            SELECT ds.id as daily_sale_id, s.id as regular_sale_id
            FROM daily_sales ds
            JOIN sales s ON ds.sale_number = s.sale_number AND ds.shift_id = s.shift_id
            WHERE ds.id = ? OR s.id = ?
        """, [data['sale_id'], data['sale_id']])

        sale_ids = cursor.fetchone()
        if not sale_ids:
            raise ValueError(f"No sale found with ID: {data['sale_id']}")

        daily_sale_id = sale_ids[0]
        regular_sale_id = sale_ids[1]

        # Get sale items from daily_sale_items
        cursor.execute("""
            SELECT si.id, si.item_id, i.name, si.quantity, si.unit_price
            FROM daily_sale_items si
            JOIN items i ON si.item_id = i.id
            WHERE si.sale_id = ?
        """, [daily_sale_id])

        sale_items = {}
        for row in cursor.fetchall():
            sale_item_data = {
                'item_id': row[1],
                'name': row[2], 
                'quantity': row[3], 
                'unit_price': row[4],
                'sale_item_id': row[0]
            }
            sale_items[str(row[0])] = sale_item_data

        if not sale_items:
            raise ValueError(f"No items found for sale: {data['sale_id']}")
            
        cursor.execute("BEGIN TRANSACTION")
        
        # Create return records in both tables
        cursor.execute("""
            INSERT INTO daily_sale_returns (sale_id, reason, total_amount, status, shift_id)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, 'completed', ?)
        """, [daily_sale_id, data['reason'], 0, shift.id])
        daily_return_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO sale_returns (sale_id, reason, total_amount, status)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, 'completed')
        """, [regular_sale_id, data['reason'], 0])
        regular_return_id = cursor.fetchone()[0]

        total_return_amount = 0
        
        if data['type'] == 'full':
            for sale_item_id, item_info in sale_items.items():
                total_price = float(item_info['quantity']) * float(item_info['unit_price'])
                total_return_amount += total_price
                
                # Insert into both return_items tables
                cursor.execute("""
                    INSERT INTO daily_return_items (return_id, item_id, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?)
                """, [daily_return_id, item_info['item_id'], item_info['quantity'], 
                     item_info['unit_price'], total_price])

                cursor.execute("""
                    INSERT INTO return_items (return_id, item_id, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?)
                """, [regular_return_id, item_info['item_id'], item_info['quantity'], 
                     item_info['unit_price'], total_price])
                
                # Update item quantity
                cursor.execute("""
                    UPDATE items
                    SET quantity = quantity + ?,
                        last_updated = GETDATE()
                    WHERE id = ?
                """, [item_info['quantity'], item_info['item_id']])
                
        else:  # Partial return
            if 'items' not in data or not data['items']:
                raise ValueError("No items specified for partial return")
                
            for item in data['items']:
                lookup_id = str(item.get('item_id', ''))
                if not lookup_id or lookup_id not in sale_items:
                    raise ValueError(f"Invalid item_id: {lookup_id}")
                
                item_info = sale_items[lookup_id]
                if float(item['quantity']) > float(item_info['quantity']):
                    raise ValueError(f"Return quantity exceeds original quantity for {item_info['name']}")
                
                total_price = float(item['quantity']) * float(item_info['unit_price'])
                total_return_amount += total_price
                
                # Insert into both return_items tables
                cursor.execute("""
                    INSERT INTO daily_return_items (return_id, item_id, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?)
                """, [daily_return_id, item_info['item_id'], item['quantity'], 
                     item_info['unit_price'], total_price])

                cursor.execute("""
                    INSERT INTO return_items (return_id, item_id, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?)
                """, [regular_return_id, item_info['item_id'], item['quantity'], 
                     item_info['unit_price'], total_price])
                
                # Update item quantity
                cursor.execute("""
                    UPDATE items
                    SET quantity = quantity + ?,
                        last_updated = GETDATE()
                    WHERE id = ?
                """, [item['quantity'], item_info['item_id']])
        
        # Update return totals in both tables
        cursor.execute("""
            UPDATE daily_sale_returns
            SET total_amount = ?
            WHERE id = ?
        """, [total_return_amount, daily_return_id])

        cursor.execute("""
            UPDATE sale_returns
            SET total_amount = ?
            WHERE id = ?
        """, [total_return_amount, regular_return_id])
        
        # Update shift totals
        cursor.execute("""
            UPDATE shifts
            SET returned_sales = ISNULL(returned_sales, 0) + ?,
                returned_items = ISNULL(returned_items, 0) + 
                    (SELECT SUM(quantity) FROM daily_return_items WHERE return_id = ?)
            WHERE id = ?
        """, [total_return_amount, daily_return_id, shift.id])
        
        cursor.execute("COMMIT")
        conn.commit()
        
        # Log the activity
        return_type = "full" if data['type'] == 'full' else "partial"
        log_activity('return', f'Sale return processed: {return_type} return for sale #{data["sale_id"]} - Amount: {total_return_amount}', 'sale_returns', regular_return_id)
        
        return jsonify({
            'success': True,
            'daily_return_id': daily_return_id,
            'regular_return_id': regular_return_id,
            'total_amount': total_return_amount
        })
        
    except Exception as e:
        if cursor:
            cursor.execute("ROLLBACK")
        if conn:
            conn.rollback()
        print(f"Error processing return: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

#endregion








#region Closing اقفال

@app.route('/closing')
@login_required
def closing():
    return render_template('closing.html')

@app.route('/get_shift_summary')
@login_required
def get_shift_summary():
    print("Getting shift summary...")
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get current active shift
        cursor.execute("""
            SELECT TOP 1 id 
            FROM shifts 
            WHERE status = 'active' 
            ORDER BY start_time DESC
        """)
        shift = cursor.fetchone()
        print(f"Active shift: {shift}")

        if not shift:
            # Return zeros instead of 404 to allow page to load
            return jsonify({
                'total_sales': 0.0,
                'total_expenses': 0.0,
                'total_returns': 0.0,
                'total_invoices': 0.0,
                'total_discounts': 0.0,
                'ewallet_amount': 0.0,
                'visa_amount': 0.0,
                'cash_amount': 0.0,
                'profit': 0.0
            })
            
        shift_id = shift[0]
        
        # Get sales summary with NULL handling
        cursor.execute("""
            SELECT 
                ISNULL(SUM(final_amount), 0) as total_sales,
                ISNULL(SUM(CASE WHEN payment_method = 'ewallet' THEN final_amount ELSE 0 END), 0) as ewallet_amount,
                ISNULL(SUM(CASE WHEN payment_method = 'visa' THEN final_amount ELSE 0 END), 0) as visa_amount,
                ISNULL(SUM(discount_amount), 0) as total_discounts
            FROM daily_sales 
            WHERE shift_id = ? AND (status = 'completed' OR status = 'done' OR status = 'pending' OR status = 'paid')
        """, shift_id)
        
        sales_data = cursor.fetchone()
        if not sales_data:
            sales_data = [0, 0, 0, 0]  # Default values if no sales
            
        total_sales = float(sales_data[0] or 0)
        ewallet_amount = float(sales_data[1] or 0)
        visa_amount = float(sales_data[2] or 0)
        total_discounts = float(sales_data[3] or 0)
        
        # Get expenses total with NULL handling
        cursor.execute("""
            SELECT ISNULL(SUM(amount), 0) 
            FROM expenses 
            WHERE shift_id = ?
        """, shift_id)
        total_expenses = float(cursor.fetchone()[0] or 0)
        
        # Get returns total with NULL handling
        cursor.execute("""
            SELECT ISNULL(SUM(sr.total_amount), 0)
            FROM daily_sale_returns sr
            JOIN daily_sales s ON sr.sale_id = s.id
            WHERE s.shift_id = ? AND sr.status = 'completed' 
        """, shift_id)
        total_returns = float(cursor.fetchone()[0] or 0)
        
        # Subtract returns from total_sales (Net Sales)
        total_sales = total_sales - total_returns
        
        # Get invoices total with NULL handling
        cursor.execute("""
            SELECT ISNULL(SUM(total_amount), 0)
            FROM invoices 
            WHERE shift_id = ? AND payment_type = 'immediate'
        """, shift_id)  # Added shift_id filter
        total_invoices = float(cursor.fetchone()[0] or 0)
        
        # Get delivery pending total with NULL handling
        cursor.execute("""
            SELECT ISNULL(SUM(final_amount), 0)
            FROM daily_sales 
            WHERE shift_id = ? AND status = 'pending'
        """, shift_id)
        delivery_pending = float(cursor.fetchone()[0] or 0)
        # Calculate cash amount (already subtracted returns from total_sales above)
        cash_amount = (total_sales - ewallet_amount - visa_amount - 
                      total_expenses - total_invoices - delivery_pending)
        
        # Calculate profit if admin
        profit = 0
        if 'admin' in session.get('permissions', []):
            # Calculate gross profit from all completed/done/paid sales
            cursor.execute("""
                SELECT ISNULL(SUM((si.unit_price - i.buy_price) * si.quantity), 0)
                FROM daily_sale_items si
                JOIN items i ON si.item_id = i.id
                JOIN daily_sales s ON si.sale_id = s.id
                WHERE s.shift_id = ? 
                AND s.status IN ('completed', 'done', 'paid')
            """, shift_id)
            gross_profit = float(cursor.fetchone()[0] or 0)
            
            # Subtract profit from returned items (sell_price - buy_price) * quantity
            cursor.execute("""
                SELECT ISNULL(SUM((ri.unit_price - i.buy_price) * ri.quantity), 0)
                FROM daily_return_items ri
                JOIN items i ON ri.item_id = i.id
                JOIN daily_sale_returns sr ON ri.return_id = sr.id
                JOIN daily_sales s ON sr.sale_id = s.id
                WHERE s.shift_id = ?
            """, shift_id)
            returned_profit = float(cursor.fetchone()[0] or 0)
            
            profit = gross_profit - returned_profit

        # Get cash box amounts for current shift (completed/done/paid sales minus return amounts)
        cursor.execute("""
            SELECT 
                cb.id, 
                cb.name, 
                ISNULL(
                    (SELECT SUM(s.final_amount)
                     FROM daily_sales s
                     WHERE s.shift_id = ? 
                     AND s.cash_box_id = cb.id
                     AND s.status IN ('completed', 'done', 'paid')), 0
                ) - ISNULL(
                    (SELECT SUM(sr.total_amount)
                     FROM daily_sale_returns sr
                     JOIN daily_sales s ON sr.sale_id = s.id
                     WHERE s.shift_id = ? 
                     AND s.cash_box_id = cb.id), 0
                ) as amount
            FROM cash_boxes cb
            WHERE cb.is_active = 1
            ORDER BY cb.is_default DESC, cb.name
        """, [shift_id, shift_id])
        cash_boxes = [{'id': row[0], 'name': row[1], 'amount': float(row[2] or 0)} for row in cursor.fetchall()]
        
        # Deduct expenses from "نقدي" cash box only
        for box in cash_boxes:
            if box['name'] == 'نقدي':
                box['amount'] -= total_expenses
                break
        
        # Calculate cash_amount as sum of all cash boxes
        cash_amount = sum(box['amount'] for box in cash_boxes)
        
        result = {
            'total_sales': total_sales,
            'total_expenses': total_expenses,
            'total_returns': total_returns,
            'total_invoices': total_invoices,
            'total_discounts': total_discounts,
            'ewallet_amount': ewallet_amount,
            'visa_amount': visa_amount,
            'cash_amount': cash_amount,
            'profit': profit - total_discounts,
            'delivery_pending': delivery_pending,
            'cash_boxes': cash_boxes
        }
        print(f"Returning data: {result}")
        return jsonify(result)
        
    except Exception as e:
        print(f"Error getting shift summary: {e}")
        import traceback
        traceback.print_exc()  # Print full stack trace
        return jsonify({'error': str(e)}), 500

@app.route('/get_shift_expenses')
@login_required
def get_shift_expenses():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get current active shift
        cursor.execute("""
            SELECT TOP 1 id FROM shifts 
            WHERE status = 'active' 
            ORDER BY start_time DESC
        """)
        shift = cursor.fetchone()
        
        if not shift:
            return jsonify([])
            
        # Get expenses for current shift
        cursor.execute("""
            SELECT id, amount, description, created_at
            FROM expenses
            WHERE shift_id = ?
            ORDER BY created_at DESC
        """, [shift[0]])
        
        expenses = []
        for row in cursor.fetchall():
            expenses.append({
                'id': row[0],
                'amount': float(row[1]),
                'description': row[2],
                'created_at': row[3].isoformat() if row[3] else None
            })
            
        return jsonify(expenses)
        
    except Exception as e:
        print(f"Error getting expenses: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/add_expense', methods=['POST'])
@login_required
def add_expense():
    try:
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()
        
        # Get current active shift
        cursor.execute("""
            SELECT TOP 1 id FROM shifts 
            WHERE status = 'active' 
            ORDER BY start_time DESC
        """)
        shift = cursor.fetchone()
        
        if not shift:
            return jsonify({'error': 'No active shift found'}), 404
        
        # Get current user
        user_id = session.get('user_id')
        
        # Add expense with user_id
        cursor.execute("""
            INSERT INTO expenses (shift_id, amount, description, user_id)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?)
        """, [shift[0], data['amount'], data['description'], user_id])
        
        expense_result = cursor.fetchone()
        expense_id = expense_result[0] if expense_result else None
        
        # Update shift totals
        cursor.execute("""
            UPDATE shifts
            SET expenses = expenses + ?
            WHERE id = ?
        """, [data['amount'], shift[0]])
        
        # Deduct expense from "نقدي" cash box
        # Get the نقدي cash box ID
        cursor.execute("SELECT id FROM cash_boxes WHERE name = N'نقدي' AND is_active = 1")
        cash_box_result = cursor.fetchone()
        if cash_box_result:
            cash_box_id = cash_box_result[0]
            # Record the expense as a transfer OUT from نقدي (negative amount)
            cursor.execute("""
                INSERT INTO cash_box_transfers (from_cash_box_id, to_cash_box_id, amount, notes, user_id)
                VALUES (?, NULL, ?, ?, ?)
            """, [cash_box_id, data['amount'], f"مصروف: {data['description']}", user_id])
        
        conn.commit()
        
        # Log the activity
        if expense_id:
            log_activity('expense', f'Expense added: {data["description"]} - Amount: {data["amount"]}', 'expenses', expense_id)
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error adding expense: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_expense/<int:expense_id>')
@login_required
def get_expense(expense_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, shift_id, amount, description, created_at FROM expenses WHERE id = ?", [expense_id])
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Expense not found'}), 404
        return jsonify({
            'id': row[0],
            'shift_id': row[1],
            'amount': float(row[2]),
            'description': row[3],
            'created_at': row[4].isoformat() if row[4] else None
        })
    except Exception as e:
        print(f"Error getting expense: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@app.route('/update_expense/<int:expense_id>', methods=['PUT'])
@login_required
def update_expense(expense_id):
    try:
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()
        
        # Get old expense data before update
        cursor.execute("SELECT amount, shift_id, description FROM expenses WHERE id = ?", [expense_id])
        old_expense = cursor.fetchone()
        if not old_expense:
            return jsonify({'error': 'Expense not found'}), 404
            
        old_amount, shift_id, old_description = old_expense
        new_amount = float(data['amount'])
        new_description = data['description']
        amount_difference = new_amount - old_amount
        
        # Update expense
        cursor.execute("""
            UPDATE expenses
            SET amount = ?, description = ?
            WHERE id = ?
        """, [new_amount, new_description, expense_id])
        
        # Update shift totals
        cursor.execute("""
            UPDATE shifts
            SET expenses = expenses + ?
            WHERE id = ?
        """, [amount_difference, shift_id])
        
        # Update cash box transfer
        cursor.execute("SELECT id FROM cash_boxes WHERE name = N'نقدي' AND is_active = 1")
        cash_box_result = cursor.fetchone()
        if cash_box_result:
            cash_box_id = cash_box_result[0]
            
            # Delete old transfer record
            cursor.execute("""
                DELETE FROM cash_box_transfers 
                WHERE from_cash_box_id = ? 
                AND amount = ? 
                AND notes = ?
            """, [cash_box_id, old_amount, f"مصروف: {old_description}"])
            
            # Create new transfer record with updated amount
            user_id = session.get('user_id')
            cursor.execute("""
                INSERT INTO cash_box_transfers (from_cash_box_id, to_cash_box_id, amount, notes, user_id)
                VALUES (?, NULL, ?, ?, ?)
            """, [cash_box_id, new_amount, f"مصروف: {new_description}", user_id])
        
        conn.commit()
        
        # Log the activity
        log_activity('expense', f'Expense updated: {new_description} - Amount: {new_amount} (was: {old_amount})', 'expenses', expense_id)
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error updating expense: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    #region Reports Shifts

@app.route('/reports_shifts')
@login_required
@permission_required('reports')
def reports_shifts():
    """Render the تقارير الورديات page where the user chooses two dates and
    sees aggregated metrics (sales, expenses, returns, orders count, invoices, profit).
    """
    # Compute initial aggregates server-side so the page shows numbers even
    # when JS is not executed or assets are slow to load.
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        # Use a broad default range (all time)
        start_bound = '1900-01-01 00:00:00'
        end_bound = '9999-12-31 23:59:59'

        cursor.execute("SELECT COUNT(*), COALESCE(SUM(sales),0), COALESCE(SUM(expenses),0) FROM shifts WHERE start_time BETWEEN ? AND ?", (start_bound, end_bound))
        r = cursor.fetchone() or (0,0,0)
        shifts_count = int(r[0] or 0)
        shifts_sales = float(r[1] or 0)
        shifts_expenses = float(r[2] or 0)

        cursor.execute("SELECT COUNT(*), COALESCE(SUM(final_amount),0) FROM sales WHERE sale_date BETWEEN ? AND ?", (start_bound, end_bound))
        r = cursor.fetchone() or (0,0)
        orders_count = int(r[0] or 0)
        sales_total = float(r[1] or 0)

        cursor.execute("SELECT COALESCE(SUM(total_amount),0) FROM sale_returns WHERE return_date BETWEEN ? AND ?", (start_bound, end_bound))
        returns_total = float(cursor.fetchone()[0] or 0)

        cursor.execute("SELECT COALESCE(SUM(total_amount),0) FROM invoices WHERE invoice_date BETWEEN ? AND ?", (start_bound, end_bound))
        invoices_total = float(cursor.fetchone()[0] or 0)

        cursor.execute(
            """
            SELECT COALESCE(SUM(si.total_price - (si.quantity * COALESCE(i.buy_price,0))),0)
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            LEFT JOIN items i ON i.id = si.item_id
            WHERE s.sale_date BETWEEN ? AND ?
            """,
            (start_bound, end_bound)
        )
        profit_est = float(cursor.fetchone()[0] or 0)

        initial = {
            'shifts_count': shifts_count,
            'shifts_sales': shifts_sales,
            'shifts_expenses': shifts_expenses,
            'orders_count': orders_count,
            'sales_total': sales_total,
            'returns_total': returns_total,
            'invoices_total': invoices_total,
            'profit_est': profit_est
        }

    except Exception:
        initial = None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return render_template('reports_shifts.html', initial=initial)


@app.route('/item_movement')
@login_required
@permission_required('item_movement')
def item_movement():
    """Render the حركة الأصناف page for item movement analysis."""
    return render_template('item_movement.html')


@app.route('/api/item_movement_data')
@login_required
def api_item_movement_data():
    """Return item movement data for the given date range and search term."""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        search_term = request.args.get('search', '').strip()

        print(f"API called with: start_date={start_date}, end_date={end_date}, search_term='{search_term}'")  # Debug log

        if not start_date or not end_date:
            return jsonify({'error': 'Start date and end date are required'}), 400

        conn = get_db()
        cursor = conn.cursor()

        # Single optimized query to get all item movement data
        query = """
            SELECT 
                i.id, i.barcode, i.name, i.buy_price, i.sell_price, i.quantity as current_stock,
                c.name as category_name, t.name as trader_name,
                
                -- Items received in the period
                COALESCE(received.total_received, 0) as received,
                
                -- Number of invoices in the period that include this item
                COALESCE(inv_count.total_invoices, 0) as invoices_count,
                
                -- Items sold from closed shifts
                COALESCE(sold_closed.total_sold_closed, 0) as sold_closed,
                
                -- Items sold from active shift
                COALESCE(sold_active.total_sold_active, 0) as sold_active
                
            FROM items i
            LEFT JOIN categories c ON i.category_id = c.id
            LEFT JOIN traders t ON i.trader_id = t.id
            
            -- Subquery for received items
            LEFT JOIN (
                SELECT ii.item_id, SUM(ii.quantity * ii.quantity_type) as total_received
                FROM invoice_items ii
                JOIN invoices inv ON ii.invoice_id = inv.id
                WHERE CONVERT(DATE, inv.invoice_date) BETWEEN ? AND ?
                GROUP BY ii.item_id
            ) received ON i.id = received.item_id
            
            -- Subquery for invoice counts containing the item
            LEFT JOIN (
                SELECT ii.item_id, COUNT(DISTINCT ii.invoice_id) as total_invoices
                FROM invoice_items ii
                JOIN invoices inv ON ii.invoice_id = inv.id
                WHERE CONVERT(DATE, inv.invoice_date) BETWEEN ? AND ?
                GROUP BY ii.item_id
            ) inv_count ON i.id = inv_count.item_id
            
            -- Subquery for sold items from closed shifts
            LEFT JOIN (
                SELECT si.item_id, SUM(si.quantity) as total_sold_closed
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                JOIN shifts sh ON s.shift_id = sh.id
                WHERE CONVERT(DATE, sh.start_time) BETWEEN ? AND ? AND sh.status = 'closed'
                GROUP BY si.item_id
            ) sold_closed ON i.id = sold_closed.item_id
            
            -- Subquery for sold items from active shifts in date range
            LEFT JOIN (
                SELECT dsi.item_id, SUM(dsi.quantity) as total_sold_active
                FROM daily_sale_items dsi
                JOIN daily_sales ds ON dsi.sale_id = ds.id
                JOIN shifts sh ON ds.shift_id = sh.id
                WHERE CONVERT(DATE, sh.start_time) BETWEEN ? AND ?
                GROUP BY dsi.item_id
            ) sold_active ON i.id = sold_active.item_id
            
            WHERE ISNULL(i.active, 1) = 1
        """

        # params order: received(start,end), invoices_count(start,end), sold_closed(start,end), sold_active(start,end)
        params = [start_date, end_date, start_date, end_date, start_date, end_date, start_date, end_date]

        # Add search filter if provided
        if search_term:
            # If search term is numeric (barcode search), do exact match
            if search_term.isdigit():
                query += " AND i.barcode = ?"
                params.append(search_term)
                print(f"Exact barcode search: {search_term}")  # Debug log
            else:
                # Text search for name
                query += " AND i.name LIKE ?"
                params.append(f'%{search_term}%')
                print(f"Name search: {search_term}")  # Debug log

        query += " ORDER BY i.name"

        print(f"Final query: {query}")  # Debug log
        print(f"Final params: {params}")  # Debug log

        cursor.execute(query, params)
        items_data = cursor.fetchall()

        print(f"Found {len(items_data)} items")  # Debug log

        results = []
        for item in items_data:
            (item_id, barcode, name, buy_price, sell_price, current_stock,
             category_name, trader_name, received, invoices_count, sold_closed, sold_active) = item

            # Convert all numeric values to float
            buy_price_val = float(buy_price or 0)
            sell_price_val = float(sell_price or 0)
            current_stock_val = float(current_stock or 0)
            received_val = float(received or 0)
            sold_closed_val = float(sold_closed or 0)
            sold_active_val = float(sold_active or 0)
            sold_total = sold_closed_val + sold_active_val

            # Calculate stock before period: current - received + sold
            stock_before = current_stock_val - received_val + sold_total

            # Calculate inventory values (only positive stock)
            current_inventory_value = max(0, current_stock_val) * buy_price_val
            inventory_after_sales = max(0, current_stock_val - sold_total) * sell_price_val

            results.append({
                'id': item_id,
                'barcode': barcode,
                'name': name,
                'category': category_name or '',
                'trader': trader_name or '',
                'buy_price': buy_price_val,
                'sell_price': sell_price_val,
                'stock_before': max(0, stock_before),  # Don't show negative
                'received': received_val,
                'invoices_count': int(invoices_count or 0),
                'sold': sold_total,
                'current_stock': max(0, current_stock_val),  # Don't show negative
                'current_inventory_value': current_inventory_value,
                'inventory_after_sales': inventory_after_sales
            })

        return jsonify({
            'success': True,
            'data': results,
            'date_range': {
                'start': start_date,
                'end': end_date
            }
        })

    except Exception as e:
        print(f"Error in item movement data: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route('/api/reports_shifts_data')
@login_required
def api_reports_shifts_data():
    """Return JSON aggregates for the given date range.
    Expected query params: start_date, end_date (YYYY-MM-DD).
    Also returns per-shift summary list and top-selling items for the range.
    """
    raw_start = request.args.get('start_date') or ''
    raw_end = request.args.get('end_date') or ''
    start_param = raw_start.strip() if raw_start else None
    end_param = raw_end.strip() if raw_end else None

    start_bound = f"{start_param} 00:00:00" if start_param else '1900-01-01 00:00:00'
    end_bound = f"{end_param} 23:59:59" if end_param else '9999-12-31 23:59:59'

    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()

        # overall shifts aggregates
        cursor.execute(
            "SELECT COUNT(*), COALESCE(SUM(sales),0), COALESCE(SUM(expenses),0) FROM shifts WHERE start_time BETWEEN ? AND ?",
            (start_bound, end_bound)
        )
        r = cursor.fetchone() or (0,0,0)
        shifts_count = int(r[0] or 0)
        shifts_sales = float(r[1] or 0)
        shifts_expenses = float(r[2] or 0)

        # sales aggregates
        cursor.execute(
            "SELECT COUNT(*), COALESCE(SUM(final_amount),0), COALESCE(SUM(delivery_fee),0) FROM sales WHERE sale_date BETWEEN ? AND ?",
            (start_bound, end_bound)
        )
        r = cursor.fetchone() or (0,0,0)
        orders_count = int(r[0] or 0)
        sales_total = float(r[1] or 0)
        delivery_fees_total = float(r[2] or 0)

        # returns
        cursor.execute("SELECT COALESCE(SUM(total_amount),0) FROM sale_returns WHERE return_date BETWEEN ? AND ?", (start_bound, end_bound))
        returns_total = float(cursor.fetchone()[0] or 0)
        
        # Subtract returns from sales_total (Net Sales)
        sales_total = sales_total - returns_total

        # invoices
        cursor.execute("SELECT COALESCE(SUM(total_amount),0), COUNT(*) FROM invoices WHERE invoice_date BETWEEN ? AND ?", (start_bound, end_bound))
        r = cursor.fetchone() or (0,0)
        invoices_total = float(r[0] or 0)
        invoices_count = int(r[1] or 0)

        # estimated profit
        cursor.execute(
            "SELECT COALESCE(SUM(si.total_price - (si.quantity * COALESCE(i.buy_price,0))),0) FROM sale_items si JOIN sales s ON s.id = si.sale_id LEFT JOIN items i ON i.id = si.item_id WHERE s.sale_date BETWEEN ? AND ?",
            (start_bound, end_bound)
        )
        estimated_profit = float(cursor.fetchone()[0] or 0)

        # per-shift breakdown
        cursor.execute("SELECT id, cashier_name, start_time, end_time, status, ISNULL(sales,0), ISNULL(expenses,0) FROM shifts WHERE start_time BETWEEN ? AND ? ORDER BY start_time DESC", (start_bound, end_bound))
        shifts_rows = cursor.fetchall()
        shifts_list = []
        for row in shifts_rows:
            sid = row[0]
            status = row[4]
            table_sales = 'daily_sales' if status == 'active' else 'sales'
            table_sale_items = 'daily_sale_items' if status == 'active' else 'sale_items'
            table_sale_returns = 'daily_sale_returns' if status == 'active' else 'sale_returns'
            table_return_items = 'daily_return_items' if status == 'active' else 'return_items'
            # orders count for the shift (from sales table)
            cursor.execute(f"SELECT COUNT(*), COALESCE(SUM(final_amount),0) FROM {table_sales} WHERE shift_id = ?", (sid,))
            sr = cursor.fetchone() or (0,0)
            ocount = int(sr[0] or 0)
            total_sales_shift = float(sr[1] or 0)
            
            # Get returns for this shift and subtract from total_sales
            cursor.execute(f"""
                SELECT ISNULL(SUM(sr.total_amount), 0)
                FROM {table_sale_returns} sr
                JOIN {table_sales} s ON sr.sale_id = s.id
                WHERE s.shift_id = ? AND sr.status = 'completed'
            """, (sid,))
            shift_returns = float(cursor.fetchone()[0] or 0)
            total_sales_shift = total_sales_shift - shift_returns

            # profit - calculate gross profit then subtract returned profit
            profit = 0
            cursor.execute(f"""
                SELECT ISNULL(SUM((si.unit_price - i.buy_price) * si.quantity), 0)
                FROM {table_sale_items} si
                JOIN items i ON si.item_id = i.id
                JOIN {table_sales} s ON si.sale_id = s.id
                WHERE s.shift_id = ? 
                AND s.status IN ('completed', 'done', 'paid')
            """, (sid,))
            gross_profit = float(cursor.fetchone()[0] or 0)
            
            # Subtract profit from returned items (sell_price - buy_price) * quantity
            cursor.execute(f"""
                SELECT ISNULL(SUM((ri.unit_price - i.buy_price) * ri.quantity), 0)
                FROM {table_return_items} ri
                JOIN items i ON ri.item_id = i.id
                JOIN {table_sale_returns} sr ON ri.return_id = sr.id
                JOIN {table_sales} s ON sr.sale_id = s.id
                WHERE s.shift_id = ?
            """, (sid,))
            returned_profit = float(cursor.fetchone()[0] or 0)
            profit = gross_profit - returned_profit

            # payment methods
            cursor.execute(f"SELECT SUM(CASE WHEN payment_method = 'ewallet' THEN final_amount ELSE 0 END), SUM(CASE WHEN payment_method = 'visa' THEN final_amount ELSE 0 END) FROM {table_sales} WHERE shift_id = ?", (sid,))
            ewallet, visa = cursor.fetchone()
            ewallet_amount = float(ewallet or 0)
            visa_amount = float(visa or 0)

            # discount
            cursor.execute(f"SELECT SUM(discount_amount) FROM {table_sales} WHERE shift_id = ?", (sid,))
            discount_amount = float(cursor.fetchone()[0] or 0)

            # cash boxes for this shift
            cursor.execute(f"""
                SELECT 
                    cb.id, 
                    cb.name, 
                    ISNULL(
                        (SELECT SUM(s.final_amount)
                         FROM {table_sales} s
                         WHERE s.shift_id = ? 
                         AND s.cash_box_id = cb.id
                         AND s.status IN ('completed', 'done', 'paid')), 0
                    ) - ISNULL(
                        (SELECT SUM(sr.total_amount)
                         FROM {table_sale_returns} sr
                         JOIN {table_sales} s ON sr.sale_id = s.id
                         WHERE s.shift_id = ? 
                         AND s.cash_box_id = cb.id), 0
                    ) as amount
                FROM cash_boxes cb
                WHERE cb.is_active = 1
                ORDER BY cb.is_default DESC, cb.name
            """, (sid, sid))
            cash_boxes = [{'id': row[0], 'name': row[1], 'amount': float(row[2] or 0)} for row in cursor.fetchall()]
            
            # Get expenses for this shift and deduct from نقدي
            cursor.execute("SELECT ISNULL(SUM(amount), 0) FROM expenses WHERE shift_id = ?", [sid])
            shift_expenses = float(cursor.fetchone()[0] or 0)
            
            # Deduct expenses from "نقدي" cash box only
            for box in cash_boxes:
                if box['name'] == 'نقدي':
                    box['amount'] -= shift_expenses
                    break
            
            # Calculate cash_amount as sum of all cash boxes
            cash_amount = sum(box['amount'] for box in cash_boxes)

            shifts_list.append({
                'id': sid,
                'cashier_name': row[1],
                'start_time': row[2].isoformat() if row[2] else None,
                'end_time': row[3].isoformat() if row[3] else None,
                'status': row[4],
                'sales_recorded': float(row[5] or 0),
                'expenses_recorded': float(row[6] or 0),
                'orders_count': ocount,
                'orders_total': total_sales_shift,
                'profit': profit,
                'ewallet_amount': ewallet_amount,
                'visa_amount': visa_amount,
                'cash_amount': cash_amount,
                'discount_amount': discount_amount,
                'cash_boxes': cash_boxes
            })

        # top items in the period (by quantity)
        # SQL Server style: select top 20
        try:
            cursor.execute(
                "SELECT TOP 20 si.item_name, SUM(si.quantity) as qty, SUM(si.total_price) as total FROM sale_items si JOIN sales s ON s.id = si.sale_id WHERE s.sale_date BETWEEN ? AND ? GROUP BY si.item_name ORDER BY SUM(si.quantity) DESC",
                (start_bound, end_bound)
            )
            top_items = [{'item_name': r[0], 'quantity': float(r[1] or 0), 'total': float(r[2] or 0)} for r in cursor.fetchall()]
        except Exception:
            top_items = []

        # Get items grouped by category (sorted by top-selling quantity) - CONSIDERING RETURNS
        try:
            cursor.execute("""
                SELECT 
                    ISNULL(c.name, 'غير مصنف') as category_name,
                    c.id as category_id,
                    SUM(si.quantity) - ISNULL((
                        SELECT SUM(ri.quantity)
                        FROM return_items ri
                        JOIN sale_returns sr ON sr.id = ri.return_id
                        JOIN items i2 ON i2.id = ri.item_id
                        WHERE sr.return_date BETWEEN ? AND ?
                        AND sr.status = 'completed'
                        AND (
                            (c.id IS NOT NULL AND i2.category_id = c.id)
                            OR (c.id IS NULL AND i2.category_id IS NULL)
                        )
                    ), 0) as net_quantity,
                    SUM(si.total_price) - ISNULL((
                        SELECT SUM(ri.total_price)
                        FROM return_items ri
                        JOIN sale_returns sr ON sr.id = ri.return_id
                        JOIN items i2 ON i2.id = ri.item_id
                        WHERE sr.return_date BETWEEN ? AND ?
                        AND sr.status = 'completed'
                        AND (
                            (c.id IS NOT NULL AND i2.category_id = c.id)
                            OR (c.id IS NULL AND i2.category_id IS NULL)
                        )
                    ), 0) as net_sales
                FROM sale_items si
                JOIN sales s ON s.id = si.sale_id
                LEFT JOIN items i ON i.id = si.item_id
                LEFT JOIN categories c ON c.id = i.category_id
                WHERE s.sale_date BETWEEN ? AND ?
                GROUP BY c.name, c.id
                ORDER BY (SUM(si.quantity) - ISNULL((
                    SELECT SUM(ri.quantity)
                    FROM return_items ri
                    JOIN sale_returns sr ON sr.id = ri.return_id
                    JOIN items i2 ON i2.id = ri.item_id
                    WHERE sr.return_date BETWEEN ? AND ?
                    AND sr.status = 'completed'
                    AND (
                        (c.id IS NOT NULL AND i2.category_id = c.id)
                        OR (c.id IS NULL AND i2.category_id IS NULL)
                    )
                ), 0)) DESC
            """, (start_bound, end_bound, start_bound, end_bound, start_bound, end_bound, start_bound, end_bound))
            
            categories_data = []
            for row in cursor.fetchall():
                cat_name = row[0]
                cat_id = row[1]
                net_qty = float(row[2] or 0)
                net_sales = float(row[3] or 0)
                
                # Skip categories with zero or negative net quantity
                if net_qty <= 0:
                    continue
                
                # Get items for this category (considering returns)
                if cat_id:
                    cursor.execute("""
                        SELECT 
                            i.name as item_name,
                            SUM(si.quantity) - ISNULL((
                                SELECT SUM(ri.quantity)
                                FROM return_items ri
                                JOIN sale_returns sr ON sr.id = ri.return_id
                                WHERE sr.return_date BETWEEN ? AND ?
                                AND sr.status = 'completed'
                                AND ri.item_id = i.id
                            ), 0) as net_quantity,
                            SUM(si.total_price) - ISNULL((
                                SELECT SUM(ri.total_price)
                                FROM return_items ri
                                JOIN sale_returns sr ON sr.id = ri.return_id
                                WHERE sr.return_date BETWEEN ? AND ?
                                AND sr.status = 'completed'
                                AND ri.item_id = i.id
                            ), 0) as net_total
                        FROM sale_items si
                        JOIN sales s ON s.id = si.sale_id
                        JOIN items i ON i.id = si.item_id
                        WHERE s.sale_date BETWEEN ? AND ?
                        AND i.category_id = ?
                        GROUP BY i.id, i.name
                        HAVING (SUM(si.quantity) - ISNULL((
                            SELECT SUM(ri.quantity)
                            FROM return_items ri
                            JOIN sale_returns sr ON sr.id = ri.return_id
                            WHERE sr.return_date BETWEEN ? AND ?
                            AND sr.status = 'completed'
                            AND ri.item_id = i.id
                        ), 0)) > 0
                        ORDER BY (SUM(si.quantity) - ISNULL((
                            SELECT SUM(ri.quantity)
                            FROM return_items ri
                            JOIN sale_returns sr ON sr.id = ri.return_id
                            WHERE sr.return_date BETWEEN ? AND ?
                            AND sr.status = 'completed'
                            AND ri.item_id = i.id
                        ), 0)) DESC
                    """, (start_bound, end_bound, start_bound, end_bound, start_bound, end_bound, cat_id, start_bound, end_bound, start_bound, end_bound))
                else:
                    # Items without category
                    cursor.execute("""
                        SELECT 
                            i.name as item_name,
                            SUM(si.quantity) - ISNULL((
                                SELECT SUM(ri.quantity)
                                FROM return_items ri
                                JOIN sale_returns sr ON sr.id = ri.return_id
                                WHERE sr.return_date BETWEEN ? AND ?
                                AND sr.status = 'completed'
                                AND ri.item_id = i.id
                            ), 0) as net_quantity,
                            SUM(si.total_price) - ISNULL((
                                SELECT SUM(ri.total_price)
                                FROM return_items ri
                                JOIN sale_returns sr ON sr.id = ri.return_id
                                WHERE sr.return_date BETWEEN ? AND ?
                                AND sr.status = 'completed'
                                AND ri.item_id = i.id
                            ), 0) as net_total
                        FROM sale_items si
                        JOIN sales s ON s.id = si.sale_id
                        LEFT JOIN items i ON i.id = si.item_id
                        WHERE s.sale_date BETWEEN ? AND ?
                        AND (i.category_id IS NULL OR i.id IS NULL)
                        GROUP BY i.id, i.name
                        HAVING (SUM(si.quantity) - ISNULL((
                            SELECT SUM(ri.quantity)
                            FROM return_items ri
                            JOIN sale_returns sr ON sr.id = ri.return_id
                            WHERE sr.return_date BETWEEN ? AND ?
                            AND sr.status = 'completed'
                            AND ri.item_id = i.id
                        ), 0)) > 0
                        ORDER BY (SUM(si.quantity) - ISNULL((
                            SELECT SUM(ri.quantity)
                            FROM return_items ri
                            JOIN sale_returns sr ON sr.id = ri.return_id
                            WHERE sr.return_date BETWEEN ? AND ?
                            AND sr.status = 'completed'
                            AND ri.item_id = i.id
                        ), 0)) DESC
                    """, (start_bound, end_bound, start_bound, end_bound, start_bound, end_bound, start_bound, end_bound, start_bound, end_bound))
                
                items = [{'item_name': r[0], 'quantity': float(r[1] or 0), 'total': float(r[2] or 0)} for r in cursor.fetchall()]
                
                # Only add category if it has items with positive net quantity
                if items:
                    categories_data.append({
                        'category_name': cat_name,
                        'category_id': cat_id,
                        'total_quantity': net_qty,
                        'total_sales': net_sales,
                        'items': items
                    })
        except Exception as e:
            import traceback
            print(f"Error fetching categories: {e}")
            traceback.print_exc()
            categories_data = []

        # calculate totals from shifts_list
        ewallet_total = sum(s['ewallet_amount'] for s in shifts_list)
        visa_total = sum(s['visa_amount'] for s in shifts_list)
        cash_total = sum(s['cash_amount'] for s in shifts_list)
        discount_total = sum(s['discount_amount'] for s in shifts_list)

        payload = {
            'success': True,
            'filters': {'start_date': raw_start, 'end_date': raw_end},
            'shifts': {'count': shifts_count, 'total_sales': shifts_sales, 'total_expenses': shifts_expenses},
            'sales': {'orders_count': orders_count, 'total_sales': sales_total, 'delivery_fees': delivery_fees_total},
            'returns': {'total_returns': returns_total},
            'invoices': {'total_invoices': invoices_total, 'count': invoices_count},
            'estimated_profit': estimated_profit,
            'shifts_list': shifts_list,
            'top_items': top_items,
            'categories_data': categories_data,
            'ewallet_total': ewallet_total,
            'visa_total': visa_total,
            'cash_total': cash_total,
            'discount_total': discount_total
        }
        return jsonify(payload)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    #endregion


@app.route('/api/profit_summary')
@login_required
def api_profit_summary():
    """Return profit summary with accurate cost calculation using item_price_history.
    Expected query params: start_date, end_date (YYYY-MM-DD).
    Returns: total_sales, cost_of_sales, total_expenses, net_profit
    """
    raw_start = request.args.get('start_date') or ''
    raw_end = request.args.get('end_date') or ''
    start_param = raw_start.strip() if raw_start else None
    end_param = raw_end.strip() if raw_end else None

    start_bound = f"{start_param} 00:00:00" if start_param else '1900-01-01 00:00:00'
    end_bound = f"{end_param} 23:59:59" if end_param else '9999-12-31 23:59:59'

    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()

        # 1. Calculate total sales from sales table (already considering returns in api_reports_shifts_data)
        cursor.execute("""
            SELECT COALESCE(SUM(final_amount), 0) 
            FROM sales 
            WHERE sale_date BETWEEN ? AND ?
        """, (start_bound, end_bound))
        total_sales = float(cursor.fetchone()[0] or 0)
        
        # Subtract returns from total sales
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) 
            FROM sale_returns 
            WHERE return_date BETWEEN ? AND ? 
            AND status = 'completed'
        """, (start_bound, end_bound))
        returns_total = float(cursor.fetchone()[0] or 0)
        total_sales = total_sales - returns_total

        # 2. Calculate cost of sales using item_price_history for accurate historical buy prices
        # For each sale item, find the buy_price at the time of sale by checking item_price_history
        cursor.execute("""
            SELECT 
                si.item_id,
                si.quantity,
                s.sale_date,
                i.buy_price as current_buy_price
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            LEFT JOIN items i ON i.id = si.item_id
            WHERE s.sale_date BETWEEN ? AND ?
        """, (start_bound, end_bound))
        
        sale_items = cursor.fetchall()
        cost_of_sales = 0
        
        for item_id, quantity, sale_date, current_buy_price in sale_items:
            if not item_id:
                continue
            
            # Try to find the buy_price at the time of sale from item_price_history
            # Get the most recent price change before or at the sale date
            cursor.execute("""
                SELECT TOP 1 new_buy_price
                FROM item_price_history
                WHERE item_id = ? AND change_date <= ?
                ORDER BY change_date DESC
            """, (item_id, sale_date))
            
            historical_price = cursor.fetchone()
            
            if historical_price:
                buy_price = float(historical_price[0] or 0)
            else:
                # No history found, use current buy_price from items table
                buy_price = float(current_buy_price or 0)
            
            cost_of_sales += buy_price * float(quantity or 0)
        
        # Subtract cost of returned items
        cursor.execute("""
            SELECT 
                ri.item_id,
                ri.quantity,
                sr.return_date,
                i.buy_price as current_buy_price
            FROM return_items ri
            JOIN sale_returns sr ON sr.id = ri.return_id
            LEFT JOIN items i ON i.id = ri.item_id
            WHERE sr.return_date BETWEEN ? AND ?
            AND sr.status = 'completed'
        """, (start_bound, end_bound))
        
        return_items = cursor.fetchall()
        
        for item_id, quantity, return_date, current_buy_price in return_items:
            if not item_id:
                continue
            
            # Find the buy_price at the time of return
            cursor.execute("""
                SELECT TOP 1 new_buy_price
                FROM item_price_history
                WHERE item_id = ? AND change_date <= ?
                ORDER BY change_date DESC
            """, (item_id, return_date))
            
            historical_price = cursor.fetchone()
            
            if historical_price:
                buy_price = float(historical_price[0] or 0)
            else:
                buy_price = float(current_buy_price or 0)
            
            cost_of_sales -= buy_price * float(quantity or 0)

        # 3. Calculate total expenses excluding delivery worker payments
        # Get expenses from expenses table - join with shifts to filter by date
        cursor.execute("""
            SELECT COALESCE(SUM(e.amount), 0)
            FROM expenses e
            JOIN shifts s ON s.id = e.shift_id
            WHERE s.start_time BETWEEN ? AND ?
            AND e.description NOT LIKE N'دفع مستحقات مندوب التوصيل%'
        """, (start_bound, end_bound))
        expenses_from_expenses_table = float(cursor.fetchone()[0] or 0)
        
        # Get employee disbursements from employee_disbursements table
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM employee_disbursements
            WHERE disbursement_date BETWEEN ? AND ?
        """, (start_bound, end_bound))
        employee_disbursements_total = float(cursor.fetchone()[0] or 0)
        
        total_expenses = expenses_from_expenses_table + employee_disbursements_total

        # 4. Calculate net profit
        net_profit = total_sales - cost_of_sales - total_expenses

        payload = {
            'success': True,
            'total_sales': total_sales,
            'cost_of_sales': cost_of_sales,
            'total_expenses': total_expenses,
            'net_profit': net_profit
        }
        return jsonify(payload)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@app.route('/delete_expense/<int:expense_id>', methods=['DELETE'])
@login_required
def delete_expense(expense_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get expense amount and description before deletion
        cursor.execute("SELECT amount, shift_id, description FROM expenses WHERE id = ?", [expense_id])
        expense = cursor.fetchone()
        if not expense:
            return jsonify({'error': 'Expense not found'}), 404
            
        amount, shift_id, description = expense
        
        # Delete expense
        cursor.execute("DELETE FROM expenses WHERE id = ?", [expense_id])
        
        # Update shift totals
        cursor.execute("""
            UPDATE shifts
            SET expenses = expenses - ?
            WHERE id = ?
        """, [amount, shift_id])
        
        # Reverse the cash box transfer (delete the transfer record)
        cursor.execute("SELECT id FROM cash_boxes WHERE name = N'نقدي' AND is_active = 1")
        cash_box_result = cursor.fetchone()
        if cash_box_result:
            cash_box_id = cash_box_result[0]
            # Delete the transfer that was created for this expense
            cursor.execute("""
                DELETE FROM cash_box_transfers 
                WHERE from_cash_box_id = ? 
                AND amount = ? 
                AND notes = ?
            """, [cash_box_id, amount, f"مصروف: {description}"])
        
        conn.commit()
        
        # Log the activity
        log_activity('expense', f'Expense deleted: {description} - Amount: {amount}', 'expenses', expense_id)
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error deleting expense: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/get_shift_details/<int:shift_id>')
@login_required
def get_shift_details(shift_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                s.id,
                s.start_time,
                s.end_time,
                s.cashier_name,
                s.sales,
                s.expenses,
                s.returned_sales,
                s.status
            FROM shifts s
            WHERE s.id = ?
        """, [shift_id])
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Shift not found'}), 404
            
        return jsonify({
            'id': row[0],
            'start_time': row[1].isoformat() if row[1] else None,
            'end_time': row[2].isoformat() if row[2] else None,
            'cashier_name': row[3],
            'sales': float(row[4]),
            'expenses': float(row[5]),
            'returned_sales': float(row[6]),
            'status': row[7]
        })
        
    except Exception as e:
        print(f"Error getting shift details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_shift_sales')
@login_required
def get_shift_sales():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT TOP 1 id FROM shifts 
            WHERE status = 'active' 
            ORDER BY start_time DESC
        """)
        shift = cursor.fetchone()
        
        if not shift:
            return jsonify([])
            
        cursor.execute("""
            SELECT id, sale_number, created_at, total_amount, discount_amount, 
                   final_amount, status
            FROM daily_sales
            WHERE shift_id = ?
            ORDER BY created_at DESC
        """, [shift[0]])
        
        sales = []
        for row in cursor.fetchall():
            sales.append({
                'id': row[0],
                'number': row[1],
                'date': row[2].isoformat() if row[2] else None,
                'total_amount': float(row[3]),
                'discount_amount': float(row[4]),
                'final_amount': float(row[5]),
                'status': row[6]
            })
            
        return jsonify(sales)
        
    except Exception as e:
        print(f"Error getting sales: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_shift_returns')
@login_required
def get_shift_returns():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT sr.id, s.sale_number, sr.return_date, sr.total_amount, sr.status
            FROM daily_sale_returns sr
            JOIN daily_sales s ON sr.sale_id = s.id
            JOIN shifts sh ON s.shift_id = sh.id
            WHERE sh.status = 'active'
            ORDER BY sr.return_date DESC
        """)
        
        returns = []
        for row in cursor.fetchall():
            # row layout: id, sale_number, return_date, total_amount, status
            returns.append({
                'id': row[0],
                'number': row[1],
                'date': row[2].isoformat() if row[2] else None,
                'total_amount': float(row[3]),
                'status': row[4]
            })
            
        return jsonify(returns)
        
    except Exception as e:
        print(f"Error getting returns: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_shift_invoices')
@login_required
def get_shift_invoices():
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT TOP 1 id FROM shifts 
            WHERE status = 'active' 
            ORDER BY start_time DESC
        """)
        shift = cursor.fetchone()
        
        if not shift:
            return jsonify([])        
        
        cursor.execute("""
            SELECT id, invoice_date, total_amount, status
            FROM invoices
            WHERE shift_id = ?
            ORDER BY invoice_date DESC
        """, [shift[0]])
        
        invoices = []
        for row in cursor.fetchall():
            invoices.append({
                'id': row[0],
                'date': row[1].isoformat() if row[1] else None,
                'total_amount': float(row[2]),
                'status': row[3]
            })
            
        return jsonify(invoices)
        
    except Exception as e:
        print(f"Error getting invoices: {e}")
        return jsonify({'error': str(e)}), 500




@app.route('/close_shift', methods=['POST'])
@login_required
def close_shift():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get current active shift
        cursor.execute("""
            SELECT TOP 1 id, cashier_name 
            FROM shifts 
            WHERE status = 'active' 
            ORDER BY start_time DESC
        """)
        current_shift = cursor.fetchone()
        
        if not current_shift:
            return jsonify({
                'success': False,
                'error': 'No active shift found'
            }), 400
        
        # Check for pending deliveries
        cursor.execute("""
            SELECT ISNULL(SUM(final_amount), 0)
            FROM daily_sales 
            WHERE shift_id = ? AND status = 'pending'
        """, [current_shift[0]])
        
        delivery_pending = float(cursor.fetchone()[0] or 0)
        
        if delivery_pending > 0:
            return jsonify({
                'success': False,
                'error': f'Cannot close shift. There are pending deliveries worth {delivery_pending:.2f}'
            }), 400
            
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")
        try:
            # Close current shift
            cursor.execute("""
                UPDATE shifts 
                SET status = 'closed',
                    end_time = GETDATE()
                WHERE id = ?
            """, [current_shift[0]])
            
            # Calculate and persist aggregates for the closing shift so the
            # shifts table contains totals even after we remove daily_* rows.
            try:
                cursor.execute("""
                    SELECT 
                        ISNULL(SUM(CONVERT(decimal(10,2), final_amount)), 0) as total_sales,
                        ISNULL((SELECT SUM(CONVERT(decimal(10,2), amount)) FROM expenses WHERE shift_id = ?), 0) as total_expenses,
                        ISNULL((SELECT SUM(CONVERT(decimal(10,2), total_amount)) FROM invoices WHERE shift_id = ?), 0) as total_invoices,
                        ISNULL((SELECT SUM(CONVERT(decimal(10,2), sr.total_amount)) FROM sale_returns sr JOIN daily_sales sa ON sr.sale_id = sa.id WHERE sa.shift_id = ?), 0) as total_returns
                """, (current_shift[0], current_shift[0], current_shift[0], current_shift[0]))

                aggregates = cursor.fetchone() or (0, 0, 0, 0)
                total_sales, total_expenses, total_invoices, total_returns = aggregates

                cursor.execute("""
                    UPDATE shifts
                    SET sales = ?, invoices = ?, expenses = ?, returned_sales = ?
                    WHERE id = ?
                """, (total_sales, total_invoices, total_expenses, total_returns, current_shift[0]))
            except Exception as e:
                # Non-fatal: log and continue with deletion
                print(f"Warning: failed to compute/update shift aggregates on close: {e}")
            
            # First delete daily_return_items
            cursor.execute("""
                DELETE dri
                FROM daily_return_items dri
                INNER JOIN daily_sale_returns dsr ON dri.return_id = dsr.id
                INNER JOIN daily_sales ds ON dsr.sale_id = ds.id
                WHERE ds.shift_id = ?
            """, [current_shift[0]])
            
            # Then delete daily_sale_returns
            cursor.execute("""
                DELETE dsr
                FROM daily_sale_returns dsr
                INNER JOIN daily_sales ds ON dsr.sale_id = ds.id
                WHERE ds.shift_id = ?
            """, [current_shift[0]])
            
            # Now delete daily_sale_items
            cursor.execute("""
                DELETE FROM daily_sale_items 
                WHERE sale_id IN (
                    SELECT id FROM daily_sales WHERE shift_id = ?
                )
            """, [current_shift[0]])
            
            # Finally delete daily_sales
            cursor.execute("""
                DELETE FROM daily_sales 
                WHERE shift_id = ?
            """, [current_shift[0]])
            
            # Create new shift with same cashier
            cursor.execute("""
                INSERT INTO shifts (
                    cashier_name, status, start_time,
                    sales, invoices, expenses, 
                    returned_sales, returned_items
                ) VALUES (
                    ?, 'active', GETDATE(),
                    0, 0, 0, 0, 0
                )
            """, [current_shift[1]])
            
            cursor.execute("COMMIT")
            conn.commit()
            
            # Log the activity
            log_activity('shift_close', f'Shift #{current_shift[0]} closed by {current_shift[1]}', 'shifts', current_shift[0])
            
            return jsonify({'success': True})
            
        except Exception as e:
            cursor.execute("ROLLBACK")
            conn.rollback()
            raise e
            
    except Exception as e:
        print(f"Error closing shift: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/print_shift_summary', methods=['POST'])
@login_required
def print_shift_summary():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get printer settings
        cursor.execute("SELECT printer_name, store_name, store_phone, store_address FROM settings WHERE id = 1")
        settings = cursor.fetchone()
        if not settings or not settings[0]:
            raise Exception("لم يتم العثور على إعدادات الطابعة")
            
        # Get current shift data with corrected query
        cursor.execute("""
            SELECT 
                s.id, 
                s.cashier_name, 
                s.start_time,
                ISNULL((SELECT SUM(CONVERT(decimal(10,2), final_amount)) 
                        FROM daily_sales 
                        WHERE shift_id = s.id), 0) as total_sales,
                ISNULL((SELECT SUM(CONVERT(decimal(10,2), amount)) 
                        FROM expenses 
                        WHERE shift_id = s.id), 0) as total_expenses,
                ISNULL((SELECT SUM(CONVERT(decimal(10,2), sr.total_amount)) 
                        FROM sale_returns sr
                        JOIN daily_sales sa ON sr.sale_id = sa.id 
                        WHERE sa.shift_id = s.id), 0) as total_returns,
                ISNULL((SELECT SUM(CONVERT(decimal(10,2), total_amount)) 
                        FROM invoices 
                        WHERE shift_id = s.id), 0) as total_invoices,
                ISNULL((SELECT SUM(CONVERT(decimal(10,2), final_amount)) 
                        FROM daily_sales 
                        WHERE shift_id = s.id 
                        AND payment_method = 'visa'), 0) as visa_amount,
                ISNULL((SELECT SUM(CONVERT(decimal(10,2), final_amount)) 
                        FROM daily_sales 
                        WHERE shift_id = s.id 
                        AND payment_method = 'ewallet'), 0) as ewallet_amount
            FROM shifts s
            WHERE s.status = 'active'
        """)
                
        shift_data = cursor.fetchone()
        if not shift_data:
            raise Exception("لم يتم العثور على وردية نشطة")

        # Get shift number separately
        cursor.execute("""
            SELECT COUNT(*) + 1 
            FROM shifts 
            WHERE start_time < (SELECT start_time FROM shifts WHERE id = ?)
        """, [shift_data[0]])
        shift_number = cursor.fetchone()[0]

        # Setup printer
        hprinter = win32print.OpenPrinter(settings[0])
        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(settings[0])
        dc.StartDoc('Shift Summary')
        dc.StartPage()

        # Get printer dimensions
        page_width = dc.GetDeviceCaps(8)  # PHYSICALWIDTH
        right_edge = page_width - int(100)

        # Print settings
        y = int(100)
        line_height = int(50)  # Increased from 40
        margin = int(100)
        
        # Create fonts with larger sizes
        header_font = win32ui.CreateFont({
            'name': 'Arial',
            'height': int(50),  # Increased from 40
            'weight': 700
        })
        normal_font = win32ui.CreateFont({
            'name': 'Arial',
            'height': int(38),  # Increased from 30
            'weight': 400
        })
        bold_font = win32ui.CreateFont({
            'name': 'Arial',
            'height': int(38),  # Increased from 30
            'weight': 700
        })

        # Print header
        dc.SelectObject(header_font)
        text_width = dc.GetTextExtent(settings[1])[0]
        dc.TextOut(right_edge - text_width, y, settings[1])  # Store name
        y += line_height

        text = "ملخص الوردية"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += line_height

        text = f"وردية رقم: {shift_number}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += int(line_height * 1.5)

        # Print shift details
        dc.SelectObject(normal_font)
        text = f"الكاشير: {shift_data[1]}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += line_height

        text = f"وقت البدء: {shift_data[2].strftime('%Y-%m-%d %I:%M %p')}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += line_height

        # Add closing time
        text = f"وقت الإقفال: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += int(line_height * 1.5)

        # Print financial summary as table
        total_sales_raw = float(shift_data[3])
        total_returns = float(shift_data[5])
        total_expenses = float(shift_data[4])
        total_invoices = float(shift_data[6])
        net_sales = total_sales_raw - total_returns  # Subtract returns from sales

        # Draw summary table header
        dc.SelectObject(header_font)
        text = "الملخص المالي"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += int(line_height * 1.5)

        # Print separator line using dashes
        dc.SelectObject(normal_font)
        separator = "=" * 40
        text_width = dc.GetTextExtent(separator)[0]
        dc.TextOut(right_edge - text_width, y, separator)
        y += int(line_height * 0.5)

        # Table rows - simpler format without borders
        dc.SelectObject(normal_font)
        
        # Row 1: Total Sales (gross)
        text = f"إجمالي المبيعات (قبل الخصم): {total_sales_raw:.2f}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += line_height

        # Row 2: Returns
        text = f"المرتجعات: ({total_returns:.2f})"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += line_height

        # Row 3: Net Sales (after returns)
        dc.SelectObject(bold_font)
        text = f"صافي المبيعات: {net_sales:.2f}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += line_height
        
        # Separator
        dc.SelectObject(normal_font)
        separator = "-" * 40
        text_width = dc.GetTextExtent(separator)[0]
        dc.TextOut(right_edge - text_width, y, separator)
        y += int(line_height * 0.3)

        # Row 4: Expenses  
        text = f"المصروفات: {total_expenses:.2f}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += line_height

        # Row 4: Expenses
        text = f"المصروفات: {total_expenses:.2f}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += line_height

        # Row 5: Invoices
        text = f"الفواتير: {total_invoices:.2f}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += line_height
        
        # Separator
        separator = "=" * 40
        text_width = dc.GetTextExtent(separator)[0]
        dc.TextOut(right_edge - text_width, y, separator)
        y += int(line_height * 1.5)

        # Payment Methods Section
        visa_amount = float(shift_data[7])
        ewallet_amount = float(shift_data[8])
        cash_amount = net_sales - visa_amount - ewallet_amount  # Use net_sales instead of total_sales

        dc.SelectObject(header_font)
        text = "طرق الدفع"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += int(line_height * 1.5)

        # Separator
        dc.SelectObject(normal_font)
        separator = "=" * 40
        text_width = dc.GetTextExtent(separator)[0]
        dc.TextOut(right_edge - text_width, y, separator)
        y += int(line_height * 0.5)

        # Payment rows
        dc.SelectObject(normal_font)
        # Payment rows
        dc.SelectObject(normal_font)
        
        # Visa
        text = f"فيزا: {visa_amount:.2f}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += line_height

        # E-wallet
        text = f"محفظة إلكترونية: {ewallet_amount:.2f}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += line_height

        # Cash
        dc.SelectObject(bold_font)
        text = f"نقدي: {cash_amount:.2f}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)
        y += line_height
        
        # Separator
        dc.SelectObject(normal_font)
        separator = "=" * 40
        text_width = dc.GetTextExtent(separator)[0]
        dc.TextOut(right_edge - text_width, y, separator)
        y += int(line_height * 1.5)

        # Get and print cash boxes (completed/done/paid sales minus return amounts)
        cursor.execute("""
            SELECT 
                cb.name, 
                ISNULL(
                    (SELECT SUM(s.final_amount)
                     FROM daily_sales s
                     WHERE s.shift_id = ? 
                     AND s.cash_box_id = cb.id
                     AND s.status IN ('completed', 'done', 'paid')), 0
                ) - ISNULL(
                    (SELECT SUM(sr.total_amount)
                     FROM daily_sale_returns sr
                     JOIN daily_sales s ON sr.sale_id = s.id
                     WHERE s.shift_id = ? 
                     AND s.cash_box_id = cb.id), 0
                ) as amount
            FROM cash_boxes cb
            WHERE cb.is_active = 1
            ORDER BY cb.is_default DESC, cb.name
        """, [shift_data[0], shift_data[0]])
        
        cash_boxes = cursor.fetchall()
        
        if cash_boxes:
            # Cash Boxes Section
            dc.SelectObject(header_font)
            text = "الصناديق"
            text_width = dc.GetTextExtent(text)[0]
            dc.TextOut(right_edge - text_width, y, text)
            y += int(line_height * 1.5)
            
            # Separator
            dc.SelectObject(normal_font)
            separator = "=" * 40
            text_width = dc.GetTextExtent(separator)[0]
            dc.TextOut(right_edge - text_width, y, separator)
            y += int(line_height * 0.5)
            
            # Print each cash box
            total_cash_boxes = 0
            for box in cash_boxes:
                box_name = box[0]
                box_amount = float(box[1])
                total_cash_boxes += box_amount
                
                text = f"{box_name}: {box_amount:.2f}"
                text_width = dc.GetTextExtent(text)[0]
                dc.TextOut(right_edge - text_width, y, text)
                y += line_height
            
            # Total row
            dc.SelectObject(bold_font)
            text = f"الإجمالي: {total_cash_boxes:.2f}"
            text_width = dc.GetTextExtent(text)[0]
            dc.TextOut(right_edge - text_width, y, text)
            y += line_height
            
            # Separator
            dc.SelectObject(normal_font)
            separator = "=" * 40
            text_width = dc.GetTextExtent(separator)[0]
            dc.TextOut(right_edge - text_width, y, separator)
            y += int(line_height * 1.5)

        # Get and print expenses table
        cursor.execute("""
            SELECT description, amount, created_at
            FROM expenses 
            WHERE shift_id = ?
            ORDER BY created_at DESC
        """, [shift_data[0]])
        
        expenses = cursor.fetchall()
        
        if expenses:
            # Expenses Table
            dc.SelectObject(header_font)
            text = "المصروفات"
            text_width = dc.GetTextExtent(text)[0]
            dc.TextOut(right_edge - text_width, y, text)
        if expenses:
            # Expenses Section
            dc.SelectObject(header_font)
            text = "المصروفات"
            text_width = dc.GetTextExtent(text)[0]
            dc.TextOut(right_edge - text_width, y, text)
            y += int(line_height * 1.5)

            # Separator
            dc.SelectObject(normal_font)
            separator = "=" * 40
            text_width = dc.GetTextExtent(separator)[0]
            dc.TextOut(right_edge - text_width, y, separator)
            y += int(line_height * 0.5)

            # Print expenses rows
            total_expenses_sum = 0
            for expense in expenses:
                description = str(expense[0])[:35]  # Truncate long descriptions
                amount = float(expense[1])
                total_expenses_sum += amount
                
                text = f"{description}: {amount:.2f}"
                text_width = dc.GetTextExtent(text)[0]
                dc.TextOut(right_edge - text_width, y, text)
                y += line_height

            # Separator
            separator = "-" * 40
            text_width = dc.GetTextExtent(separator)[0]
            dc.TextOut(right_edge - text_width, y, separator)
            y += int(line_height * 0.3)

            # Total row
            dc.SelectObject(bold_font)
            text = f"إجمالي المصروفات: {total_expenses_sum:.2f}"
            text_width = dc.GetTextExtent(text)[0]
            dc.TextOut(right_edge - text_width, y, text)
            y += line_height
            
            # Separator
            dc.SelectObject(normal_font)
            separator = "=" * 40
            text_width = dc.GetTextExtent(separator)[0]
            dc.TextOut(right_edge - text_width, y, separator)
            y += int(line_height * 2)

        # Print footer
        dc.SelectObject(normal_font)
        text = f"تاريخ الطباعة: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}"
        text_width = dc.GetTextExtent(text)[0]
        dc.TextOut(right_edge - text_width, y, text)

        # End print job
        dc.EndPage()
        dc.EndDoc()
        dc.DeleteDC()
        win32print.ClosePrinter(hprinter)

        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error printing shift summary: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


#endregion







#region Invoices الفواتير 

@app.route('/invoices')
@login_required
def invoices_page():
    conn = get_db()
    cursor = conn.cursor()
    
    # Get traders
    cursor.execute("SELECT id, name FROM traders WHERE ISNULL(active,1) = 1 ORDER BY name")
    traders = [dict(zip(['id', 'name'], row)) for row in cursor.fetchall()]
    
    # Get companies
    cursor.execute("SELECT id, name FROM companies ORDER BY name")
    companies = [dict(zip(['id', 'name'], row)) for row in cursor.fetchall()]
    
    return render_template('invoices.html', traders=traders, companies=companies)


# Supplier balances (رصيد الموردين)
@app.route('/supplier_balances')
@login_required
@permission_required('supplier_balances')
def supplier_balances():
    conn = get_db()
    cursor = conn.cursor()

    # Get active traders for filter dropdown
    cursor.execute("SELECT id, name FROM traders WHERE ISNULL(active,1) = 1 ORDER BY name")
    traders = [dict(zip(['id', 'name'], row)) for row in cursor.fetchall()]

    return render_template('supplier_balances.html', traders=traders)


@app.route('/get_supplier_balances')
@login_required
def get_supplier_balances():
    try:
        conn = get_db()
        cursor = conn.cursor()

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        trader_id = request.args.get('trader_id')

        # Default dates if not provided
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = '1900-01-01'

        # Build base query for supplier balances; optionally filter by trader_id
        query = """
            SELECT t.id as trader_id, t.name,
                   SUM(ISNULL(i.total_amount,0)) AS total_subtotal,
                   SUM(ISNULL(i.paid_amount,0)) AS total_paid,
                   SUM(ISNULL(i.total_amount,0)) - SUM(ISNULL(i.paid_amount,0)) AS balance
            FROM invoices i
            INNER JOIN traders t ON i.trader_id = t.id
            WHERE i.invoice_date >= ? AND i.invoice_date <= ?
              AND ISNULL(t.active,1) = 1
        """

        params = [start_date + " 00:00:00", end_date + " 23:59:59"]

        if trader_id:
            try:
                tid = int(trader_id)
            except Exception:
                tid = None
            if tid:
                query += " AND t.id = ?"
                params.append(tid)

        query += """
            GROUP BY t.id, t.name
            HAVING SUM(ISNULL(i.total_amount,0)) > 0
            ORDER BY t.name
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()

        result = []
        for r in rows:
            result.append({
                'trader_id': r[0],
                'name': r[1],
                'total_subtotal': float(r[2] or 0),
                'total_paid': float(r[3] or 0),
                'balance': float(r[4] or 0)
            })

        return jsonify(result)
    except Exception as e:
        print(f"Error getting supplier balances: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass


@app.route('/get_supplier_invoices/<int:trader_id>')
@login_required
def get_supplier_invoices(trader_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d 23:59:59')
        if not start_date:
            start_date = '1900-01-01'

        query = """
            SELECT i.id, i.invoice_date, i.subtotal, i.paid_amount, i.remaining_amount, i.payment_type, i.status
            FROM invoices i
            WHERE i.trader_id = ? AND i.invoice_date >= ? AND i.invoice_date <= ?
            ORDER BY i.invoice_date DESC
        """

        cursor.execute(query, (trader_id, start_date, end_date))
        rows = cursor.fetchall()

        invoices = []
        for r in rows:
            invoices.append({
                'id': r[0],
                'invoice_date': r[1].isoformat() if r[1] else None,
                'subtotal': float(r[2] or 0),
                'paid_amount': float(r[3] or 0),
                'remaining': float(r[4] or 0),
                'payment_type': r[5],
                'status': r[6]
            })

        return jsonify(invoices)
    except Exception as e:
        print(f"Error getting supplier invoices: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_invoices')
@login_required
def get_invoices():
    try:
        conn = get_db()
        cursor = conn.cursor()

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        trader_id = request.args.get('trader_id')
        company_id = request.args.get('company_id')
        payment_status = request.args.get('payment_status')

        # Build query
        query = """
            SELECT i.id, i.invoice_date, i.total_amount, i.paid_amount, 
                   i.remaining_amount, i.payment_status,
                   CASE 
                       WHEN i.trader_id IS NOT NULL THEN t.name
                       ELSE c.name
                   END as entity_name
            FROM invoices i
            LEFT JOIN traders t ON i.trader_id = t.id
            LEFT JOIN companies c ON i.company_id = c.id
            WHERE 1=1
        """
        params = []

        if start_date:
            query += " AND i.invoice_date >= ?"
            params.append(start_date + " 00:00:00")
        if end_date:
            query += " AND i.invoice_date <= ?"
            params.append(end_date + " 23:59:59")
        if trader_id:
            query += " AND i.trader_id = ?"
            params.append(trader_id)
        if company_id:
            query += " AND i.company_id = ?"
            params.append(company_id)
        if payment_status:
            query += " AND i.payment_status = ?"
            params.append(payment_status)

        query += " ORDER BY i.invoice_date DESC"

        cursor.execute(query, params)
        invoices = []
        for row in cursor.fetchall():
            invoices.append({
                'id': row[0],
                'invoice_date': row[1].isoformat() if row[1] else None,
                'total_amount': float(row[2] or 0),
                'paid_amount': float(row[3] or 0),
                'remaining_amount': float(row[4] or 0),
                'payment_status': row[5],
                'entity_name': row[6]
            })

        # Calculate summary
        total = sum(inv['total_amount'] for inv in invoices)
        paid = sum(inv['paid_amount'] for inv in invoices)
        remaining = sum(inv['remaining_amount'] for inv in invoices)

        summary = {
            'total': total,
            'paid': paid,
            'remaining': remaining
        }

        return jsonify({
            'invoices': invoices,
            'summary': summary
        })

    except Exception as e:
        print(f"Error getting invoices: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Build filters
        filters = []
        params = []
        
        if request.args.get('start_date'):
            filters.append("invoice_date >= ?")
            params.append(request.args.get('start_date'))
        
        if request.args.get('end_date'):
            filters.append("invoice_date <= ?")
            params.append(request.args.get('end_date'))
        
        if request.args.get('trader_id'):
            filters.append("trader_id = ?")
            params.append(request.args.get('trader_id'))
        
        if request.args.get('company_id'):
            filters.append("company_id = ?")
            params.append(request.args.get('company_id'))
        
        if request.args.get('payment_status'):
            filters.append("payment_status = ?")
            params.append(request.args.get('payment_status'))
        
        # Default to current shift if no filters
        if not filters:
            cursor.execute("""
                SELECT TOP 1 id FROM shifts 
                WHERE status = 'active' 
                ORDER BY start_time DESC
            """)
            current_shift = cursor.fetchone()
            if current_shift:
                filters.append("shift_id = ?")
                params.append(current_shift[0])
        
        where_clause = " AND ".join(filters) if filters else "1=1"
        
        # Get invoices
        query = f"""
            SELECT i.*, 
                   COALESCE(t.name, c.name) as entity_name
            FROM invoices i
            LEFT JOIN traders t ON i.trader_id = t.id
            LEFT JOIN companies c ON i.company_id = c.id
            WHERE {where_clause}
            ORDER BY i.invoice_date DESC
        """
        
        cursor.execute(query, params)
        invoices = []
        total_amount = 0
        total_paid = 0
        
        for row in cursor.fetchall():
            invoice = {
                'id': row[0],
                'invoice_date': row[1].isoformat() if row[1] else None,
                'total_amount': float(row[2]),
                'paid_amount': float(row[8] or 0),
                'remaining_amount': float(row[9] or 0),
                'payment_status': row[13],
                'entity_name': row[-1]
            }
            invoices.append(invoice)
            total_amount += invoice['total_amount']
            total_paid += invoice['paid_amount']
        
        summary = {
            'total': total_amount,
            'paid': total_paid,
            'remaining': total_amount - total_paid
        }
        
        return jsonify({
            'invoices': invoices,
            'summary': summary
        })
        
    except Exception as e:
        print(f"Error getting invoices: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/process_payment', methods=['POST'])
@login_required
def process_payment():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        trader_id = data.get('trader_id')
        payment_amount = float(data.get('amount', 0))
        cash_box_id = data.get('cash_box_id')
        notes = data.get('notes', '')
        
        if not trader_id or payment_amount <= 0 or not cash_box_id:
            return jsonify({'error': 'Missing required fields'}), 400

        conn = get_db()
        cursor = conn.cursor()
        
        # Get user info
        user_id = session.get('user_id')
        
        # Get all unpaid/partial invoices for this trader, ordered by date (oldest first)
        cursor.execute("""
            SELECT id, total_amount, paid_amount, remaining_amount
            FROM invoices
            WHERE trader_id = ? 
            AND payment_status IN ('unpaid', 'partial')
            AND remaining_amount > 0
            ORDER BY invoice_date ASC
        """, [trader_id])
        
        invoices = cursor.fetchall()
        
        if not invoices:
            return jsonify({'error': 'No unpaid invoices found for this supplier'}), 400
        
        remaining_payment = payment_amount
        payments_made = []
        
        cursor.execute("BEGIN TRANSACTION")
        
        # Distribute payment across invoices
        for invoice in invoices:
            if remaining_payment <= 0:
                break
                
            invoice_id = invoice[0]
            total_amount = float(invoice[1])
            current_paid = float(invoice[2] or 0)
            current_remaining = float(invoice[3])
            
            # Calculate how much to pay for this invoice
            amount_to_pay = min(remaining_payment, current_remaining)
            
            new_paid = current_paid + amount_to_pay
            new_remaining = current_remaining - amount_to_pay
            
            # Determine payment status
            if new_remaining <= 0:
                payment_status = 'paid'
            elif new_paid > 0:
                payment_status = 'partial'
            else:
                payment_status = 'unpaid'
            
            # Update invoice
            cursor.execute("""
                UPDATE invoices 
                SET paid_amount = ?, remaining_amount = ?, payment_status = ?
                WHERE id = ?
            """, [new_paid, new_remaining, payment_status, invoice_id])
            
            # Insert payment record
            cursor.execute("""
                INSERT INTO invoice_payments (invoice_id, amount, payment_date, notes)
                VALUES (?, ?, GETDATE(), ?)
            """, [invoice_id, amount_to_pay, notes or f'Payment via cash box #{cash_box_id}'])
            
            # Record in cash box transfers (money going OUT to supplier)
            cursor.execute("""
                INSERT INTO cash_box_transfers (
                    from_cash_box_id, 
                    amount, 
                    transfer_date, 
                    notes,
                    user_id
                )
                VALUES (?, ?, GETDATE(), ?, ?)
            """, [cash_box_id, amount_to_pay, f'Payment to supplier - Invoice #{invoice_id}', user_id])
            
            payments_made.append({
                'invoice_id': invoice_id,
                'amount': amount_to_pay
            })
            
            remaining_payment -= amount_to_pay
        
        cursor.execute("COMMIT")
        conn.commit()
        
        # Log activity
        log_activity('payment', f'Supplier payment: {payment_amount} distributed across {len(payments_made)} invoices', 'invoices', trader_id)

        return jsonify({
            'success': True,
            'payments_made': payments_made,
            'remaining_amount': remaining_payment
        })

    except Exception as e:
        if cursor:
            try:
                cursor.execute("ROLLBACK")
            except:
                pass
        if conn:
            conn.rollback()
        print(f"Error processing payment: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/update_invoice_balances', methods=['POST'])
@login_required
def update_invoice_balances():
    try:
        data = request.get_json()
        invoice_id = data.get('invoice_id')
        paid_amount = data.get('paid_amount')
        remaining_amount = data.get('remaining_amount')

        if not invoice_id or paid_amount is None or remaining_amount is None:
            return jsonify({'error': 'Missing required fields'}), 400

        conn = get_db()
        cursor = conn.cursor()

        # Get total amount
        cursor.execute("SELECT total_amount FROM invoices WHERE id = ?", [invoice_id])
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Invoice not found'}), 404

        total_amount = float(row[0])

        # Determine payment status
        if remaining_amount <= 0:
            payment_status = 'paid'
        elif paid_amount > 0:
            payment_status = 'partial'
        else:
            payment_status = 'unpaid'

        # Update invoice
        cursor.execute("""
            UPDATE invoices 
            SET paid_amount = ?, remaining_amount = ?, payment_status = ?
            WHERE id = ?
        """, [paid_amount, remaining_amount, payment_status, invoice_id])

        conn.commit()

        return jsonify({'success': True})

    except Exception as e:
        print(f"Error updating invoice balances: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_invoice_payments/<int:invoice_id>')
@login_required
def get_invoice_payments(invoice_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, amount, payment_date, notes
            FROM invoice_payments
            WHERE invoice_id = ?
            ORDER BY payment_date DESC
        """, [invoice_id])

        payments = []
        for row in cursor.fetchall():
            payments.append({
                'id': row[0],
                'amount': float(row[1] or 0),
                'payment_date': row[2].isoformat() if row[2] else None,
                'notes': row[3]
            })

        return jsonify(payments)

    except Exception as e:
        print(f"Error getting invoice payments: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_invoice_details/<int:invoice_id>')
@login_required
def get_invoice_details(invoice_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get invoice header
        cursor.execute("""
            SELECT i.id, i.invoice_date, i.total_amount, i.discount_amount, 
                   i.paid_amount, i.remaining_amount, i.payment_status,
                   CASE 
                       WHEN i.trader_id IS NOT NULL THEN t.name
                       ELSE c.name
                   END as entity_name
            FROM invoices i
            LEFT JOIN traders t ON i.trader_id = t.id
            LEFT JOIN companies c ON i.company_id = c.id
            WHERE i.id = ?
        """, [invoice_id])

        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Invoice not found'}), 404

        invoice = {
            'id': row[0],
            'invoice_date': row[1].isoformat() if row[1] else None,
            'total_amount': float(row[2] or 0),
            'discount_amount': float(row[3] or 0),
            'paid_amount': float(row[4] or 0),
            'remaining_amount': float(row[5] or 0),
            'payment_status': row[6],
            'entity_name': row[7]
        }

        # Get invoice items
        cursor.execute("""
            SELECT ii.quantity, ii.quantity_type, ii.buy_price, ii.sell_price, 
                   ii.total_price, i.name as item_name
            FROM invoice_items ii
            JOIN items i ON ii.item_id = i.id
            WHERE ii.invoice_id = ?
        """, [invoice_id])

        items = []
        for row in cursor.fetchall():
            items.append({
                'quantity': row[0],
                'quantity_type': row[1],
                'buy_price': float(row[2] or 0),
                'sell_price': float(row[3] or 0),
                'total_price': float(row[4] or 0),
                'item_name': row[5]
            })

        invoice['items'] = items

        return jsonify(invoice)

    except Exception as e:
        print(f"Error getting invoice details: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get invoice details
        cursor.execute("""
            SELECT 
                i.id,
                i.invoice_date,
                i.total_amount,
                i.subtotal,
                i.discount_value,
                i.discount_type,
                i.discount_amount,
                i.payment_type,
                i.paid_amount,
                i.remaining_amount,
                i.payment_status,
                COALESCE(t.name, c.name) as entity_name
            FROM invoices i
            LEFT JOIN traders t ON i.trader_id = t.id
            LEFT JOIN companies c ON i.company_id = c.id
            WHERE i.id = ?
        """, [invoice_id])
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Invoice not found'}), 404
            
        invoice = {
            'id': row[0],
            'invoice_date': row[1].isoformat() if row[1] else None,
            'total_amount': float(row[2] or 0),
            'subtotal': float(row[3] or 0),
            'discount_value': float(row[4] or 0),
            'discount_type': row[5],
            'discount_amount': float(row[6] or 0),
            'payment_type': row[7],
            'paid_amount': float(row[8] or 0),
            'remaining_amount': float(row[9] or 0),
            'payment_status': row[10],
            'entity_name': row[11]
        }
        
        # Get invoice items
        cursor.execute("""
            SELECT 
                ii.id,
                ii.item_id,
                i.name as item_name,
                ii.quantity,
                ii.quantity_type,
                ii.buy_price,
                ii.sell_price,
                ii.total_price
            FROM invoice_items ii
            JOIN items i ON ii.item_id = i.id
            WHERE ii.invoice_id = ?
        """, [invoice_id])
        
        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row[0],
                'item_id': row[1],
                'item_name': row[2],
                'quantity': int(row[3]),
                'quantity_type': int(row[4]),
                'buy_price': float(row[5]),
                'sell_price': float(row[6]),
                'total_price': float(row[7])
            })
        
        invoice['items'] = items
        return jsonify(invoice)
        
    except Exception as e:
        print(f"Error getting invoice details: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


#endregion







#region Shifts الورديات

@app.route('/shifts')
@login_required
@permission_required('shifts')
def shifts():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
         SELECT id, cashier_name, start_time, end_time, status,
             -- If the shift is active, compute from daily_sales; otherwise use persisted shifts.sales
             CASE WHEN ISNULL(status, '') = 'active' 
               THEN ISNULL((SELECT SUM(final_amount) FROM daily_sales WHERE shift_id = s.id), 0)
               ELSE ISNULL(s.sales, 0)
             END as total_sales,
                   ISNULL((SELECT SUM(amount) FROM expenses WHERE shift_id = s.id), 0) as total_expenses,
                   ISNULL((SELECT SUM(total_amount) FROM invoices WHERE shift_id = s.id), 0) as total_invoices
            FROM shifts s
            ORDER BY start_time DESC
        """)
        
        shifts = [dict(zip([
            'id', 'cashier_name', 'start_time', 'end_time', 'status',
            'total_sales', 'total_expenses', 'total_invoices'
        ], row)) for row in cursor.fetchall()]
        
        return render_template('shifts.html', shifts=shifts)
    finally:
        cursor.close()
        conn.close()

@app.route('/get_shift_summary_shifts/<int:shift_id>')
@login_required
def get_shift_summary_shifts(shift_id):
    print(f"Getting shift summary for shift ID: {shift_id}")
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get shift status
        cursor.execute("SELECT status FROM shifts WHERE id = ?", [shift_id])
        shift_row = cursor.fetchone()
        shift_status = shift_row[0] if shift_row else 'closed'

        table_sales = 'daily_sales' if shift_status == 'active' else 'sales'
        table_sale_items = 'daily_sale_items' if shift_status == 'active' else 'sale_items'
        table_sale_returns = 'daily_sale_returns' if shift_status == 'active' else 'sale_returns'
        table_return_items = 'daily_return_items' if shift_status == 'active' else 'return_items'

        # Get sales summary with NULL handling
        cursor.execute(f"""
            SELECT 
                ISNULL(SUM(final_amount), 0) as total_sales,
                ISNULL(SUM(CASE WHEN payment_method = 'ewallet' THEN final_amount ELSE 0 END), 0) as ewallet_amount,
                ISNULL(SUM(CASE WHEN payment_method = 'visa' THEN final_amount ELSE 0 END), 0) as visa_amount,
                ISNULL(SUM(discount_amount), 0) as total_discounts
            FROM {table_sales} 
            WHERE shift_id = ? AND status = 'completed'
        """, [shift_id])
        
        sales_data = cursor.fetchone()
        if not sales_data:
            sales_data = [0, 0, 0, 0]  # Default values if no sales
            
        total_sales = float(sales_data[0] or 0)
        ewallet_amount = float(sales_data[1] or 0)
        visa_amount = float(sales_data[2] or 0)
        total_discounts = float(sales_data[3] or 0)
        
        # Get expenses total
        cursor.execute("""
            SELECT ISNULL(SUM(amount), 0) 
            FROM expenses 
            WHERE shift_id = ?
        """, [shift_id])
        total_expenses = float(cursor.fetchone()[0] or 0)
        
        # Get returns total
        cursor.execute(f"""
            SELECT ISNULL(SUM(sr.total_amount), 0)
            FROM {table_sale_returns} sr
            JOIN {table_sales} s ON sr.sale_id = s.id
            WHERE s.shift_id = ? AND sr.status = 'completed'
        """, [shift_id])
        total_returns = float(cursor.fetchone()[0] or 0)
        
        # Subtract returns from total_sales (Net Sales)
        total_sales = total_sales - total_returns
        
        # Get invoices total
        cursor.execute("""
            SELECT ISNULL(SUM(total_amount), 0)
            FROM invoices 
            WHERE shift_id = ? AND payment_type = 'immediate'
        """, [shift_id])
        total_invoices = float(cursor.fetchone()[0] or 0)
        
        # Calculate cash amount (already subtracted returns from total_sales above)
        cash_amount = (total_sales - ewallet_amount - visa_amount - 
                      total_expenses - total_invoices)
        
        # Get orders count
        cursor.execute(f"SELECT COUNT(*) FROM {table_sales} WHERE shift_id = ? AND status = 'completed'", [shift_id])
        orders_count = cursor.fetchone()[0] or 0
        
        # Calculate profit if admin
        profit = 0
        if 'admin' in session.get('permissions', []):
            # Calculate gross profit from all completed/done/paid sales
            cursor.execute(f"""
                SELECT ISNULL(SUM((si.unit_price - i.buy_price) * si.quantity), 0)
                FROM {table_sale_items} si
                JOIN items i ON si.item_id = i.id
                JOIN {table_sales} s ON si.sale_id = s.id
                WHERE s.shift_id = ? 
                AND s.status IN ('completed', 'done', 'paid')
            """, [shift_id])
            gross_profit = float(cursor.fetchone()[0] or 0)
            
            # Subtract profit from returned items (sell_price - buy_price) * quantity
            cursor.execute(f"""
                SELECT ISNULL(SUM((ri.unit_price - i.buy_price) * ri.quantity), 0)
                FROM {table_return_items} ri
                JOIN items i ON ri.item_id = i.id
                JOIN {table_sale_returns} sr ON ri.return_id = sr.id
                JOIN {table_sales} s ON sr.sale_id = s.id
                WHERE s.shift_id = ?
            """, [shift_id])
            returned_profit = float(cursor.fetchone()[0] or 0)
            
            profit = gross_profit - returned_profit

        # Get cash box amounts for this shift (completed/done/paid sales minus return amounts)
        cursor.execute("""
            SELECT 
                cb.id, 
                cb.name, 
                ISNULL(
                    (SELECT SUM(s.final_amount)
                     FROM {table_sales} s
                     WHERE s.shift_id = ? 
                     AND s.cash_box_id = cb.id
                     AND s.status IN ('completed', 'done', 'paid')), 0
                ) - ISNULL(
                    (SELECT SUM(sr.total_amount)
                     FROM {table_sale_returns} sr
                     JOIN {table_sales} s ON sr.sale_id = s.id
                     WHERE s.shift_id = ? 
                     AND s.cash_box_id = cb.id), 0
                ) as amount
            FROM cash_boxes cb
            WHERE cb.is_active = 1
            ORDER BY cb.is_default DESC, cb.name
        """.format(table_sale_returns=table_sale_returns, table_sales=table_sales), [shift_id, shift_id])
        cash_boxes = [{'id': row[0], 'name': row[1], 'amount': float(row[2] or 0)} for row in cursor.fetchall()]

        # Deduct expenses from "نقدي" cash box only
        for box in cash_boxes:
            if box['name'] == 'نقدي':
                box['amount'] -= total_expenses
                break

        # Calculate cash_amount as sum of all cash boxes
        cash_amount = sum(box['amount'] for box in cash_boxes)

        result = {
            'total_sales': total_sales,
            'total_expenses': total_expenses,
            'total_returns': total_returns,
            'total_invoices': total_invoices,
            'total_discounts': total_discounts,
            'ewallet_amount': ewallet_amount,
            'visa_amount': visa_amount,
            'cash_amount': cash_amount,
            'orders_count': orders_count,
            'profit': profit,
            'cash_boxes': cash_boxes
        }
        print(f"Returning data: {result}")
        return jsonify(result)
        
    except Exception as e:
        print(f"Error getting shift summary: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/get_shift_sales_shifts/<int:shift_id>')
@login_required
def get_shift_sales_shifts(shift_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Get shift status to determine table names
        cursor.execute("SELECT status FROM shifts WHERE id = ?", [shift_id])
        shift_row = cursor.fetchone()
        shift_status = shift_row[0] if shift_row else 'closed'
        table_sales = 'daily_sales' if shift_status == 'active' else 'sales'
        
        cursor.execute(f"""
            SELECT 
                id,
                sale_number,
                created_at,
                CONVERT(float, final_amount) as final_amount,
                payment_method
            FROM {table_sales} 
            WHERE shift_id = ? 
            ORDER BY created_at DESC
        """, [shift_id])
        
        # Map the columns in the correct order
        columns = ['id', 'sale_number', 'created_at', 'final_amount', 'payment_method']
        
        sales = []
        for row in cursor.fetchall():
            sale_dict = {}
            for i, column in enumerate(columns):
                # Handle datetime conversion for JSON
                if column == 'created_at' and row[i]:
                    sale_dict[column] = row[i].isoformat()
                else:
                    sale_dict[column] = row[i]
            sales.append(sale_dict)
            
        print(f"Found {len(sales)} sales")  # Debug log
        return jsonify({'sales': sales})
        
    except Exception as e:
        print(f"Error getting sales: {e}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        cursor.close()
        conn.close()


@app.route('/get_shifts')
@login_required
def get_shifts():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, cashier_name, start_time, end_time, status
            FROM shifts
            ORDER BY start_time DESC
        """)
        shifts = []
        for row in cursor.fetchall():
            # Check if this is the current active shift
            is_current = row[4] == 'active'
            shifts.append({
                'id': row[0],
                'name': f"وردية {row[0]} - {row[1]}",
                'cashier_name': row[1],
                'start_time': row[2].strftime('%Y-%m-%d %I:%M %p') if row[2] else None,
                'end_time': row[3].strftime('%Y-%m-%d %I:%M %p') if row[3] else None,
                'status': row[4],
                'is_current': is_current,
                'date': row[2].strftime('%Y-%m-%d') if row[2] else None
            })

        return jsonify({'success': True, 'shifts': shifts})

    except Exception as e:
        print('Error fetching shifts:', e)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@app.route('/get_shift_fees/<int:shift_id>')
@login_required
def get_shift_fees(shift_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        # Aggregate fees per worker for the given shift
        cursor.execute("""
            SELECT dw.id, dw.name, dw.phone, COUNT(ds.id) as completed_count, ISNULL(SUM(ds.delivery_fee),0) as total_fees
            FROM daily_sales ds
            JOIN delivery_workers dw ON dw.id = ds.delivery_worker_id
            WHERE ds.shift_id = ? AND ds.status = 'done'
            GROUP BY dw.id, dw.name, dw.phone
        """, [shift_id])

        fees = []
        for row in cursor.fetchall():
            fees.append({
                'worker_id': row[0],
                'worker_name': row[1],
                'worker_phone': row[2],
                'completed_count': int(row[3]),
                'total_fees': float(row[4])
            })

        return jsonify({'success': True, 'fees': fees})

    except Exception as e:
        print('Error fetching shift fees:', e)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@app.route('/get_shifts_overview')
@login_required
def get_shifts_overview():
    """Return aggregated summary across shifts and per-shift breakdown with optional date filters."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Read day-only inputs and expand to full-day bounds
        raw_start = request.args.get('start_date') or ''
        raw_end = request.args.get('end_date') or ''
        start_param = raw_start.strip() if raw_start else None
        end_param = raw_end.strip() if raw_end else None
        start_bound = f"{start_param} 00:00:00" if start_param else None
        end_bound = f"{end_param} 23:59:59" if end_param else None

        # Count shifts in range
        if start_bound and end_bound:
            cursor.execute("SELECT COUNT(*) FROM shifts WHERE start_time BETWEEN ? AND ?", [start_bound, end_bound])
        elif start_bound:
            cursor.execute("SELECT COUNT(*) FROM shifts WHERE start_time >= ?", [start_bound])
        elif end_bound:
            cursor.execute("SELECT COUNT(*) FROM shifts WHERE start_time <= ?", [end_bound])
        else:
            cursor.execute("SELECT COUNT(*) FROM shifts")
        total_shifts = cursor.fetchone()[0] or 0

        # Build alias-aware fragments for subqueries
        ds_frag = ''
        ds2_frag = ''
        no_alias_frag = ''
        expense_frag = ''
        if start_bound:
            ds_frag += ' AND ds.created_at >= ?'
            ds2_frag += ' AND ds2.created_at >= ?'
            no_alias_frag += ' AND created_at >= ?'
            expense_frag += ' AND e.created_at >= ?'
        if end_bound:
            ds_frag += ' AND ds.created_at <= ?'
            ds2_frag += ' AND ds2.created_at <= ?'
            no_alias_frag += ' AND created_at <= ?'
            expense_frag += ' AND e.created_at <= ?'

        query = f"""
            SELECT s.id,
                   s.cashier_name,
                -- Use daily_sales for active shifts, otherwise use stored s.sales
                CASE WHEN ISNULL(s.status, '') = 'active' 
                    THEN ISNULL((SELECT SUM(final_amount) FROM daily_sales ds WHERE ds.shift_id = s.id {ds_frag}),0)
                    ELSE ISNULL(s.sales, 0)
                END as total_sales,
                   ISNULL((SELECT SUM(amount) FROM expenses e WHERE e.shift_id = s.id {expense_frag}),0) as total_expenses,
                -- Orders count: for active shift count rows in daily_sales; otherwise count from sales
                CASE WHEN ISNULL(s.status,'') = 'active'
                    THEN ISNULL((SELECT COUNT(*) FROM daily_sales WHERE shift_id = s.id {no_alias_frag}),0)
                    ELSE ISNULL((SELECT COUNT(*) FROM sales WHERE shift_id = s.id),0)
                END as orders_count,
           -- Estimated profit: choose source depending on shift status
           CASE WHEN ISNULL(s.status,'') = 'active'
            THEN ISNULL((SELECT SUM(si.total_price - (si.quantity * ISNULL(i.buy_price,0)))
                     FROM sale_items si
                     JOIN daily_sales ds2 ON si.sale_id = ds2.id
                     JOIN items i ON si.item_id = i.id
                     WHERE ds2.shift_id = s.id {ds2_frag}),0)
            ELSE ISNULL((SELECT SUM(si.total_price - (si.quantity * ISNULL(i.buy_price,0)))
                     FROM sale_items si
                     JOIN sales sal ON si.sale_id = sal.id
                     JOIN items i2 ON si.item_id = i2.id
                     WHERE sal.shift_id = s.id),0)
           END as estimated_profit
            FROM shifts s
            ORDER BY s.start_time DESC
        """

        # Bind parameters in subquery order: ds (for total_sales), e (for expenses),
        # no_alias (for orders_count), ds2 (for estimated_profit)
        bind_params = []
        # total_sales (ds)
        if start_bound: bind_params.append(start_bound)
        if end_bound: bind_params.append(end_bound)
        # total_expenses (e)
        if start_bound: bind_params.append(start_bound)
        if end_bound: bind_params.append(end_bound)
        # orders_count (no_alias)
        if start_bound: bind_params.append(start_bound)
        if end_bound: bind_params.append(end_bound)
        # estimated_profit (ds2)
        if start_bound: bind_params.append(start_bound)
        if end_bound: bind_params.append(end_bound)

        # Debug: log final query and parameters to help diagnose filtering issues
        try:
            print('DEBUG get_shifts_overview: start_bound=', start_bound, 'end_bound=', end_bound)
            print('DEBUG get_shifts_overview: final SQL:\n', query)
            print('DEBUG get_shifts_overview: bind_params=', bind_params)
            cursor.execute(query, bind_params)
        except Exception as exec_err:
            import traceback
            print('ERROR executing get_shifts_overview query:', exec_err)
            traceback.print_exc()
            # Re-raise so the outer exception handler returns an error JSON to the client
            raise

        shifts = []
        totals = {'total_sales': 0.0, 'total_expenses': 0.0, 'orders_count': 0, 'estimated_profit': 0.0}
        for row in cursor.fetchall():
            sid = row[0]
            sales = float(row[2] or 0)
            expenses = float(row[3] or 0)
            orders_count = int(row[4] or 0)
            profit = float(row[5] or 0)
            shifts.append({
                'id': sid,
                'cashier_name': row[1],
                'total_sales': sales,
                'total_expenses': expenses,
                'orders_count': orders_count,
                'estimated_profit': profit
            })
            totals['total_sales'] += sales
            totals['total_expenses'] += expenses
            totals['orders_count'] += orders_count
            totals['estimated_profit'] += profit

        return jsonify({
            'success': True,
            'total_shifts': total_shifts,
            'totals': totals,
            'shifts': shifts
        })

    except Exception as e:
        print('Error building shifts overview:', e)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@app.route('/download_shifts_report')
@login_required
def download_shifts_report():
    """Return a CSV report summarizing shifts (download)."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        # Support optional date range query params and normalize
        raw_start = request.args.get('start_date') or ''
        raw_end = request.args.get('end_date') or ''
        start_param = raw_start.replace('T', ' ').strip() if raw_start else None
        end_param = raw_end.replace('T', ' ').strip() if raw_end else None

        ds_frag = ''
        no_alias_frag = ''
        expense_frag = ''
        if start_param:
            ds_frag += ' AND ds.created_at >= ?'
            no_alias_frag += ' AND created_at >= ?'
            expense_frag += ' AND e.created_at >= ?'
        if end_param:
            ds_frag += ' AND ds.created_at <= ?'
            no_alias_frag += ' AND created_at <= ?'
            expense_frag += ' AND e.created_at <= ?'

        query = f"""
          SELECT s.id, s.cashier_name, s.start_time, s.end_time,
                -- For CSV: use daily_sales for active shifts, otherwise stored s.sales
                CASE WHEN ISNULL(s.status,'') = 'active'
                    THEN ISNULL((SELECT SUM(final_amount) FROM daily_sales ds WHERE ds.shift_id = s.id {ds_frag}),0)
                    ELSE ISNULL(s.sales, 0)
                END as total_sales,
                ISNULL((SELECT SUM(amount) FROM expenses e WHERE e.shift_id = s.id {expense_frag}),0) as total_expenses,
                CASE WHEN ISNULL(s.status,'') = 'active'
                    THEN ISNULL((SELECT COUNT(*) FROM daily_sales WHERE shift_id = s.id {no_alias_frag}),0)
                    ELSE ISNULL((SELECT COUNT(*) FROM sales WHERE shift_id = s.id),0)
                END as orders_count,
                CASE WHEN ISNULL(s.status,'') = 'active'
                    THEN ISNULL((SELECT SUM(si.total_price - (si.quantity * ISNULL(i.buy_price,0)))
                                 FROM sale_items si
                                 JOIN daily_sales ds2 ON si.sale_id = ds2.id
                                 JOIN items i ON si.item_id = i.id
                                 WHERE ds2.shift_id = s.id {ds_frag}),0)
                    ELSE ISNULL((SELECT SUM(si.total_price - (si.quantity * ISNULL(i.buy_price,0)))
                                 FROM sale_items si
                                 JOIN sales sal ON si.sale_id = sal.id
                                 JOIN items i2 ON si.item_id = i2.id
                                 WHERE sal.shift_id = s.id),0)
                END as estimated_profit
            FROM shifts s
            ORDER BY s.start_time DESC
        """

        bind_params = []
        # Bind parameters in order of subqueries
        # total_sales (ds)
        if start_param: bind_params.append(start_param)
        if end_param: bind_params.append(end_param)
        # total_expenses (e)
        if start_param: bind_params.append(start_param)
        if end_param: bind_params.append(end_param)
        # orders_count (no alias)
        if start_param: bind_params.append(start_param)
        if end_param: bind_params.append(end_param)
        # estimated_profit (ds_frag used again)
        if start_param: bind_params.append(start_param)
        if end_param: bind_params.append(end_param)

        cursor.execute(query, bind_params)

        # Build CSV
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['shift_id', 'cashier', 'start_time', 'end_time', 'total_sales', 'total_expenses', 'orders_count'])
        for row in cursor.fetchall():
            writer.writerow([
                row[0],
                row[1],
                row[2].strftime('%Y-%m-%d') if row[2] else '',
                row[3].strftime('%Y-%m-%d') if row[3] else '',
                float(row[4] or 0),
                float(row[5] or 0),
                int(row[6] or 0)
            ])

        csv_data = output.getvalue()
        output.close()
        return (csv_data, 200, {
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': 'attachment; filename=shifts_report.csv'
        })

    except Exception as e:
        print('Error generating shifts report:', e)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@app.route('/get_shift_fees_all')
@login_required
def get_shift_fees_all():
    # Support query params: worker_id, shift_id
    worker_id = request.args.get('worker_id')
    shift_id = request.args.get('shift_id')
    try:
        conn = get_db()
        cursor = conn.cursor()
        # Aggregate fees from both daily_sales (recent) and sales (historical)
        # We'll union the two tables and then group by delivery worker and shift
        query = """
            SELECT dw.id, dw.name, t.shift_id, COUNT(t.id) as completed_count, ISNULL(SUM(t.delivery_fee),0) as total_fees
            FROM (
                SELECT id, delivery_worker_id, shift_id, delivery_fee FROM daily_sales WHERE status IN ('done','completed')
                UNION ALL
                SELECT id, delivery_worker_id, shift_id, delivery_fee FROM sales WHERE status IN ('done','completed')
            ) t
            JOIN delivery_workers dw ON dw.id = t.delivery_worker_id
            WHERE 1=1
        """
        params = []
        if worker_id:
            query += " AND dw.id = ?"
            params.append(worker_id)
        if shift_id:
            query += " AND t.shift_id = ?"
            params.append(shift_id)
        query += " GROUP BY dw.id, dw.name, t.shift_id"

        cursor.execute(query, params)
        results = []
        for row in cursor.fetchall():
            results.append({
                'worker_id': row[0],
                'worker_name': row[1],
                'shift_id': row[2],
                'completed_count': int(row[3]),
                'total_fees': float(row[4])
            })

        # Optionally add shift_name via another query for convenience
        shift_names = {}
        if results:
            cursor.execute("SELECT id, cashier_name FROM shifts WHERE id IN (" + ",".join(['?']*len(results)) + ")", [r['shift_id'] for r in results])
            for r in cursor.fetchall():
                shift_names[r[0]] = f"وردية {r[0]} - {r[1]}"
            for r in results:
                r['shift_name'] = shift_names.get(r['shift_id'], f"وردية {r['shift_id']}")

        return jsonify({'success': True, 'fees': results})

    except Exception as e:
        print('Error fetching all shift fees:', e)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@app.route('/get_shift_fee_orders')
@login_required
def get_shift_fee_orders():
    worker_id = request.args.get('worker_id')
    shift_id = request.args.get('shift_id')
    try:
        conn = get_db()
        cursor = conn.cursor()
        # We'll fetch completed/done orders from both daily_sales (recent) and sales (historical)
        # Include delivery_worker_id and shift_id in SELECT so we can return them to the client
        q1 = """
            SELECT id, sale_number, final_amount, delivery_fee, created_at, customer_name,
                   customer_phone, address_line1, address_line2, address_line3, delivery_worker_id, shift_id
            FROM daily_sales
            WHERE status IN ('done','completed')
        """
        q2 = """
            SELECT id, sale_number, final_amount, delivery_fee, created_at, customer_name,
                   customer_phone, address_line1, address_line2, address_line3, delivery_worker_id, shift_id
            FROM sales
            WHERE status IN ('done','completed')
        """

        params1 = []
        params2 = []
        if worker_id:
            q1 += " AND delivery_worker_id = ?"
            q2 += " AND delivery_worker_id = ?"
            params1.append(worker_id)
            params2.append(worker_id)
        if shift_id:
            q1 += " AND shift_id = ?"
            q2 += " AND shift_id = ?"
            params1.append(shift_id)
            params2.append(shift_id)

        final_query = q1 + "\nUNION ALL\n" + q2 + "\nORDER BY created_at DESC"
        all_params = params1 + params2
        print('DEBUG /get_shift_fee_orders executing SQL:')
        print(final_query)
        print('DEBUG params:', all_params)
        cursor.execute(final_query, all_params)

        rows = cursor.fetchall()
        print(f'DEBUG /get_shift_fee_orders fetched rows: {len(rows)}')

        orders = []
        for row in rows:
            # row mapping: id, sale_number, final_amount, delivery_fee, created_at, customer_name, customer_phone, addr1, addr2, addr3, delivery_worker_id, shift_id
            addr_parts = [row[7], row[8], row[9]] if len(row) > 9 else []
            full_address = ' - '.join([p for p in addr_parts if p]) if addr_parts else '-'
            created = row[4]
            try:
                created_str = created.strftime('%Y-%m-%d %I:%M %p') if hasattr(created, 'strftime') else str(created)
            except Exception:
                created_str = str(created)

            orders.append({
                'id': row[0],
                'sale_number': row[1],
                'final_amount': float(row[2]) if row[2] is not None else 0,
                'delivery_fee': float(row[3]) if row[3] is not None else 0,
                'created_at': created_str,
                'customer_name': row[5],
                'customer_phone': row[6] if len(row) > 6 else '-',
                'address': full_address,
                'delivery_worker_id': row[10] if len(row) > 10 else None,
                'shift_id': row[11] if len(row) > 11 else None
            })

        resp = {'success': True, 'orders': orders}
        if request.args.get('debug') == '1':
            # include the SQL and params that were used and the row count for debugging
            resp['debug_sql'] = final_query
            resp['debug_params'] = all_params
            resp['debug_row_count'] = len(rows)
        return jsonify(resp)

    except Exception as e:
        print('Error fetching shift fee orders:', e)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@app.route('/delivery_fees_by_worker')
@login_required
def delivery_fees_by_worker():
    # Render the dedicated page for viewing fees by worker and shift
    return render_template('delivery_fees_by_worker.html')


@app.route('/get_completed_orders_by_shift/<int:shift_id>/<int:delivery_worker_id>')
@login_required
def get_completed_orders_by_shift(shift_id, delivery_worker_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        # Determine shift status: if the selected shift is active, use daily_sales (current shift)
        # otherwise use historical sales table.
        cursor.execute("SELECT status FROM shifts WHERE id = ?", [shift_id])
        shift_row = cursor.fetchone()
        if not shift_row:
            return jsonify({'success': False, 'error': 'الوردية غير موجودة'}), 404

        shift_status = shift_row[0]
        orders = []

        if shift_status == 'active':
            # Current/active shift - read from daily_sales
            cursor.execute("""
                SELECT
                    ds.id,
                    ds.sale_number,
                    ds.final_amount,
                    ds.delivery_fee,
                    ds.created_at,
                    ds.customer_name,
                    ds.customer_phone,
                    ds.address_line1,
                    ds.address_line2,
                    ds.address_line3,
                    ds.status
                FROM daily_sales ds
                WHERE ds.delivery_worker_id = ?
                AND (ds.status = 'done' OR ds.status = 'paid')
                AND ds.shift_id = ?
                ORDER BY ds.created_at DESC
            """, [delivery_worker_id, shift_id])

            for row in cursor.fetchall():
                addr_parts = [row[7], row[8], row[9]]
                full_address = ' - '.join([p for p in addr_parts if p]) if any(addr_parts) else '-'
                orders.append({
                    'id': row[0],
                    'sale_number': row[1],
                    'final_amount': float(row[2]),
                    'delivery_fee': float(row[3]),
                    'created_at': row[4].strftime('%Y-%m-%d %I:%M %p'),
                    'completed_at': row[4].strftime('%Y-%m-%d %I:%M %p'),
                    'customer_name': row[5] or '-',
                    'customer_phone': row[6] or '-',
                    'address': full_address,
                    'status': row[10]
                })
        else:
            # Closed/previous shift - read from historical sales table
            cursor.execute("""
                SELECT
                    s.id,
                    s.sale_number,
                    s.final_amount,
                    s.delivery_fee,
                    s.created_at,
                    s.customer_name,
                    s.customer_phone,
                    s.address_line1,
                    s.address_line2,
                    s.address_line3,
                    s.status
                FROM sales s
                WHERE s.delivery_worker_id = ?
                AND s.status = 'done'
                AND s.shift_id = ?
                ORDER BY s.created_at DESC
            """, [delivery_worker_id, shift_id])

            for row in cursor.fetchall():
                addr_parts = [row[7], row[8], row[9]]
                full_address = ' - '.join([p for p in addr_parts if p]) if any(addr_parts) else '-'
                orders.append({
                    'id': row[0],
                    'sale_number': row[1],
                    'final_amount': float(row[2]),
                    'delivery_fee': float(row[3]),
                    'created_at': row[4].strftime('%Y-%m-%d %I:%M %p'),
                    'completed_at': row[4].strftime('%Y-%m-%d %I:%M %p'),
                    'customer_name': row[5] or '-',
                    'customer_phone': row[6] or '-',
                    'address': full_address,
                    'status': row[10]
                })

        return jsonify({
            'success': True,
            'orders': orders
        })

    except Exception as e:
        print(f"Error fetching completed orders by shift: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/pay_delivery_fees_by_shift', methods=['POST'])
@login_required
def pay_delivery_fees_by_shift():
    try:
        data = request.get_json()
        delivery_worker_id = data.get('delivery_worker_id')
        shift_id = data.get('shift_id')
        amount = data.get('amount')

        if not all([delivery_worker_id, shift_id, amount]):
            return jsonify({'success': False, 'error': 'البيانات غير مكتملة'}), 400

        # Validate amount
        try:
            amount = float(amount)
            if amount <= 0:
                return jsonify({'success': False, 'error': 'المبلغ يجب أن يكون رقمًا موجبًا'}), 400
        except ValueError:
            return jsonify({'success': False, 'error': 'المبلغ غير صالح'}), 400

        conn = get_db()
        cursor = conn.cursor()

        try:
            conn.autocommit = True  # Ensure transaction works

            # Get delivery worker name
            cursor.execute("SELECT name FROM delivery_workers WHERE id = ?", [delivery_worker_id])
            worker = cursor.fetchone()
            if not worker:
                return jsonify({'success': False, 'error': 'عامل التوصيل غير موجود'}), 404

            worker_name = worker[0]

            # Determine the active/current shift to record this expense under.
            # Behavior requested: always record fees in the active shift if one exists;
            # otherwise fall back to the provided shift_id.
            cursor.execute("SELECT id, cashier_name, start_time FROM shifts WHERE status = 'active'")
            active_row = cursor.fetchone()
            if active_row:
                recorded_shift_id = active_row[0]
                recorded_shift_label = f"وردية {active_row[0]} - {active_row[1]}" if active_row[1] else f"وردية {active_row[0]}"
                recorded_shift_start = active_row[2]
            else:
                # No active shift found: fall back to provided shift_id
                recorded_shift_id = shift_id
                cursor.execute("SELECT id, cashier_name, start_time FROM shifts WHERE id = ?", [shift_id])
                srow2 = cursor.fetchone()
                if srow2:
                    recorded_shift_label = f"وردية {srow2[0]} - {srow2[1]}" if srow2[1] else f"وردية {srow2[0]}"
                    recorded_shift_start = srow2[2]
                else:
                    recorded_shift_label = f"وردية {shift_id}"
                    recorded_shift_start = None

            # Prepare description including the original (target) shift label for traceability
            cursor.execute("SELECT id, cashier_name FROM shifts WHERE id = ?", [shift_id])
            orig_row = cursor.fetchone()
            if orig_row:
                orig_label = f"وردية {orig_row[0]} - {orig_row[1]}" if orig_row[1] else f"وردية {orig_row[0]}"
            else:
                orig_label = f"وردية {shift_id}"

            description = f'دفع مستحقات مندوب التوصيل - {worker_name} (الوردية المدفوعة: {orig_label})'

            # Try to insert shift_date into expenses if schema supports it; otherwise fallback.
            try:
                if recorded_shift_start:
                    cursor.execute("""
                        INSERT INTO expenses (shift_id, amount, description, shift_date)
                        VALUES (?, ?, ?, ?)
                    """, [recorded_shift_id, amount, description, recorded_shift_start])
                else:
                    cursor.execute("""
                        INSERT INTO expenses (shift_id, amount, description)
                        VALUES (?, ?, ?)
                    """, [recorded_shift_id, amount, description])
            except Exception as e_ins:
                # If the DB doesn't have shift_date column, retry without it
                print(f"Warning: could not insert shift_date field: {e_ins}; retrying without shift_date")
                cursor.execute("""
                    INSERT INTO expenses (shift_id, amount, description)
                    VALUES (?, ?, ?)
                """, [recorded_shift_id, amount, description])


            # Update recorded shift expenses safely
            cursor.execute("""
                UPDATE shifts
                SET expenses = COALESCE(expenses, 0) + ?
                WHERE id = ?
            """, [amount, recorded_shift_id])

            # Mark orders as paid for this shift and worker (if they exist in daily_sales for the original shift)
            cursor.execute("""
                UPDATE daily_sales
                SET status = 'paid'
                WHERE delivery_worker_id = ?
                AND shift_id = ?
                AND status = 'done'
            """, [delivery_worker_id, shift_id])

            conn.commit()
            print(f"Expense recorded under recorded_shift_id={recorded_shift_id} (orig_shift={shift_id})")
            return jsonify({'success': True, 'message': 'تم دفع رسوم التوصيل بنجاح', 'recorded_shift_id': recorded_shift_id, 'original_shift_id': shift_id})

        except Exception as e:
            conn.rollback()
            print(f"Error paying delivery fees by shift: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    except Exception as e:
        print(f"Error in pay_delivery_fees_by_shift: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/get_shift_expenses_shifts/<int:shift_id>')
@login_required
def get_shift_expenses_shifts(shift_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT description, amount, created_at
            FROM expenses 
            WHERE shift_id = ?
            ORDER BY created_at DESC
        """, [shift_id])
        
        expenses = []
        for row in cursor.fetchall():
            expenses.append({
                'description': row[0],
                'amount': float(row[1]),
                'created_at': row[2].isoformat() if row[2] else None,
            })
        
        return jsonify({'expenses': expenses})
    finally:
        cursor.close()
        conn.close()

@app.route('/get_shift_returns_shifts/<int:shift_id>')
@login_required
def get_shift_returns_shifts(shift_id):
    print(f"Loading returns for shift ID: {shift_id}")
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get shift status to determine table names
        cursor.execute("SELECT status FROM shifts WHERE id = ?", [shift_id])
        shift_row = cursor.fetchone()
        shift_status = shift_row[0] if shift_row else 'closed'
        table_sales = 'daily_sales' if shift_status == 'active' else 'sales'
        table_sale_returns = 'daily_sale_returns' if shift_status == 'active' else 'sale_returns'
        
        cursor.execute(f"""
            SELECT 
                sr.id,
                s.sale_number,
                CONVERT(float, sr.total_amount) as total_amount,
                sr.reason,
                sr.{'return_date' if shift_status == 'closed' else 'created_at'} as created_at
            FROM {table_sale_returns} sr
            JOIN {table_sales} s ON sr.sale_id = s.id
            WHERE s.shift_id = ? 
            ORDER BY sr.{'return_date' if shift_status == 'closed' else 'created_at'} DESC
        """, [shift_id])
        
        returns = []
        for row in cursor.fetchall():
            returns.append({
                'id': row[0],
                'sale_number': row[1],
                'total_amount': float(row[2] or 0),
                'reason': row[3],
                'created_at': row[4].isoformat() if row[4] else None
            })
        
        print(f"Found {len(returns)} returns")
        return jsonify({'returns': returns})
        
    except Exception as e:
        print(f"Error in get_shift_returns_shifts: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_shift_invoices_shifts/<int:shift_id>')
@login_required
def get_shift_invoices_shifts(shift_id):
    print(f"Loading invoices for shift ID: {shift_id}")
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                i.id,
                i.id as invoice_number,  -- Using ID as invoice number since it's not in schema
                t.name as supplier_name,  -- Changed from suppliers to traders
                CONVERT(float, i.total_amount) as total_amount,
                i.invoice_date as created_at  -- Using invoice_date from schema
            FROM invoices i
            LEFT JOIN traders t ON i.trader_id = t.id  -- Changed from suppliers to traders
            WHERE i.shift_id = ?
            ORDER BY i.invoice_date DESC
        """, [shift_id])
        
        invoices = []
        for row in cursor.fetchall():
            invoices.append({
                'id': row[0],
                'invoice_number': row[1],
                'supplier_name': row[2] or 'Unknown',  # Fallback for NULL
                'total_amount': float(row[3] or 0),
                'created_at': row[4].isoformat() if row[4] else None
            })
        
        print(f"Found {len(invoices)} invoices")
        return jsonify({'invoices': invoices})
        
    except Exception as e:
        print(f"Error in get_shift_invoices_shifts: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/get_sale_details_shifts/<int:sale_id>')
@login_required
def get_sale_details_shifts(sale_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get sale header details - No changes needed here
        cursor.execute("""
            SELECT 
                s.id, s.sale_number, s.sale_date, s.total_amount,
                s.subtotal, s.discount_amount, s.delivery_fee,
                s.final_amount, s.payment_method, s.customer_name,
                s.customer_phone
            FROM sales s
            WHERE s.id = ?
        """, [sale_id])
        
        sale = cursor.fetchone()
        if not sale:
            return jsonify({'error': 'Sale not found'}), 404
            
        # Fix the join condition for returned items
        cursor.execute("""
            SELECT 
                si.item_name, 
                si.quantity, 
                si.unit_price,
                si.total_price, 
                ISNULL((
                    SELECT SUM(ri.quantity)
                    FROM sale_returns sr
                    JOIN return_items ri ON sr.id = ri.return_id
                    WHERE sr.sale_id = si.sale_id
                    AND ri.item_id = si.item_id
                ), 0) as returned_quantity
            FROM sale_items si
            WHERE si.sale_id = ?
        """, [sale_id])
        
        items = cursor.fetchall()
        
        sale_data = {
            'id': sale[0],
            'sale_number': sale[1],
            'sale_date': sale[2].isoformat() if sale[2] else None,
            'total_amount': float(sale[3]),
            'subtotal': float(sale[4]),
            'discount_amount': float(sale[5]),
            'delivery_fee': float(sale[6]),
            'final_amount': float(sale[7]),
            'payment_method': sale[8],
            'customer_name': sale[9],
            'customer_phone': sale[10],
            'items': [{
                'item_name': item[0],
                'quantity': float(item[1]),
                'unit_price': float(item[2]),
                'total_price': float(item[3]),
                'returned_quantity': float(item[4])
            } for item in items]
        }
        
        return jsonify(sale_data)
        
    except Exception as e:
        print(f"Error getting sale details: {e}")
        import traceback
        traceback.print_exc()  # Add this for better error tracking
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route('/get_return_details_shifts/<int:return_id>')
@login_required
def get_return_details_shifts(return_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get return header details
        cursor.execute("""
            SELECT 
                sr.id, s.sale_number, sr.return_date,
                sr.total_amount, sr.reason, sr.status,
                s.customer_name, s.customer_phone
            FROM sale_returns sr
            JOIN sales s ON sr.sale_id = s.id
            WHERE sr.id = ?
        """, [return_id])
        
        return_data = cursor.fetchone()
        if not return_data:
            return jsonify({'error': 'Return not found'}), 404
            
        # Get returned items
        cursor.execute("""
            SELECT 
                i.name as item_name,
                ri.quantity,
                ri.unit_price,
                ri.total_price
            FROM return_items ri
            JOIN items i ON ri.item_id = i.id
            WHERE ri.return_id = ?
        """, [return_id])
        
        items = cursor.fetchall()
        
        result = {
            'id': return_data[0],
            'sale_number': return_data[1],
            'return_date': return_data[2].isoformat() if return_data[2] else None,
            'total_amount': float(return_data[3]),
            'reason': return_data[4],
            'status': return_data[5],
            'customer_name': return_data[6],
            'customer_phone': return_data[7],
            'items': [{
                'item_name': item[0],
                'quantity': float(item[1]),
                'unit_price': float(item[2]),
                'total_price': float(item[3])
            } for item in items]
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error getting return details: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_invoice_details_shifts/<int:invoice_id>')
@login_required
def get_invoice_details_shifts(invoice_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get invoice header details
        cursor.execute("""
            SELECT 
                i.id, i.invoice_date, i.total_amount,
                i.subtotal, i.discount_amount,
                i.paid_amount, i.remaining_amount,
                i.payment_type, i.status,
                t.name as trader_name,
                c.name as company_name
            FROM invoices i
            LEFT JOIN traders t ON i.trader_id = t.id
            LEFT JOIN companies c ON i.company_id = c.id
            WHERE i.id = ?
        """, [invoice_id])
        
        invoice = cursor.fetchone()
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
            
        # Get invoice items
        cursor.execute("""
            SELECT 
                i.name as item_name,
                ii.quantity,
                ii.buy_price,
                ii.sell_price,
                ii.total_price
            FROM invoice_items ii
            JOIN items i ON ii.item_id = i.id
            WHERE ii.invoice_id = ?
        """, [invoice_id])
        
        items = cursor.fetchall()
        
        result = {
            'id': invoice[0],
            'invoice_date': invoice[1].isoformat() if invoice[1] else None,
            'total_amount': float(invoice[2]),
            'subtotal': float(invoice[3]),
            'discount_amount': float(invoice[4]),
            'paid_amount': float(invoice[5]),
            'remaining_amount': float(invoice[6]),
            'payment_type': invoice[7],
            'status': invoice[8],
            'trader_name': invoice[9],
            'company_name': invoice[10],
            'items': [{
                'item_name': item[0],
                'quantity': float(item[1]),
                'buy_price': float(item[2]),
                'sell_price': float(item[3]),
                'total_price': float(item[4])
            } for item in items]
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error getting invoice details: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
#endregion

#region Database Initialization Endpoint
@app.route('/init_db', methods=['GET', 'POST'])
def init_db_route():
    """Initialize database and create all tables - WARNING: Use with caution!"""
    try:
        from database.init_db import init_database
        
        # Call the initialization function
        init_database()
        
        return jsonify({
            'success': True,
            'message': 'Database initialized successfully! All tables created.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Database initialization failed'
        }), 500
#endregion


if __name__ == '__main__':
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint}: {rule.rule}")
    
    app.run(host='0.0.0.0', port=19523, debug=True)
