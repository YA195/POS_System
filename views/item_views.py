"""Item management views."""
from flask import Blueprint, render_template, request, jsonify
from controllers.item_controller import ItemController
from models.category import Category
from models.company import Company
from database.db import get_db
from utils.auth import login_required, permission_required

item_bp = Blueprint('items', __name__)


@item_bp.route('/items')
@login_required
@permission_required('items')
def items():
    """Render items page."""
    try:
        # Get categories with proper structure
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.name, c.section_id, s.name as section_name
            FROM categories c
            LEFT JOIN sections s ON c.section_id = s.id
            WHERE ISNULL(c.active, 1) = 1
            ORDER BY s.name, c.name
        """)
        categories_data = cursor.fetchall()
        
        categories = [{
            'id': row[0],
            'name': row[1],
            'section_id': row[2],
            'section_name': row[3]
        } for row in categories_data]
        
        # Get traders
        cursor.execute("""
            SELECT id, name 
            FROM traders 
            WHERE ISNULL(active, 1) = 1
            ORDER BY name
        """)
        traders_data = cursor.fetchall()
        
        traders = [{
            'id': row[0],
            'name': row[1]
        } for row in traders_data]
        
        return render_template('Items.html', categories=categories, traders=traders)
    except Exception as e:
        print(f"Error loading items page: {e}")
        return render_template('Items.html', categories=[], traders=[])


@item_bp.route('/get_items')
@login_required
def get_items():
    """Get all items as JSON."""
    try:
        items = ItemController.get_all_items()
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@item_bp.route('/get_item/<barcode>')
@login_required
def get_item(barcode):
    """Get item by barcode."""
    try:
        from models.item import Item
        item = Item.get_by_barcode(barcode)
        
        if item:
            return jsonify({'success': True, 'item': item})
        else:
            return jsonify({'success': False, 'message': 'Item not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@item_bp.route('/get_item_Sell/<barcode>')
@login_required
def get_item_sell(barcode):
    """Get item by barcode for sales (POS)."""
    try:
        from models.item import Item
        item_data = Item.get_by_barcode(barcode)
        
        if not item_data:
            return jsonify({'error': 'Item not found'}), 404
        
        # Format item for sales - match schema columns
        # Schema: id, barcode, name, category_id, buy_price, sell_price, quantity, trader_id, active, barcode2
        item = {
            'id': item_data[0] if len(item_data) > 0 else None,
            'barcode': item_data[1] if len(item_data) > 1 else '',
            'name': item_data[2] if len(item_data) > 2 else '',
            'category_id': item_data[3] if len(item_data) > 3 else None,
            'buy_price': float(item_data[4]) if len(item_data) > 4 and item_data[4] else 0,
            'sell_price': float(item_data[5]) if len(item_data) > 5 and item_data[5] else 0,
            'quantity': item_data[6] if len(item_data) > 6 else 0,
            'trader_id': item_data[7] if len(item_data) > 7 else None,
            'active': item_data[8] if len(item_data) > 8 else 1
        }
        
        return jsonify(item)
            
    except Exception as e:
        print(f"Error in get_item_sell: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@item_bp.route('/save_item', methods=['POST'])
@login_required
@permission_required('items')
def save_item():
    """Create a new item."""
    try:
        data = request.get_json()
        print(f"Received data: {data}")
        item_id = ItemController.create_item(data)
        print(f"Item created with ID: {item_id}")
        return jsonify({'success': True, 'item_id': item_id})
    except ValueError as e:
        print(f"ValueError in save_item: {e}")
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        print(f"Exception in save_item: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@item_bp.route('/update_item/<int:item_id>', methods=['PUT'])
@login_required
@permission_required('items')
def update_item(item_id):
    """Update an existing item."""
    try:
        data = request.get_json()
        ItemController.update_item(item_id, data)
        return jsonify({'success': True, 'message': 'Item updated successfully'})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@item_bp.route('/delete_item/<int:item_id>', methods=['DELETE'])
@login_required
@permission_required('items')
def delete_item(item_id):
    """Delete an item."""
    try:
        ItemController.delete_item(item_id)
        return jsonify({'success': True, 'message': 'Item deleted successfully'})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@item_bp.route('/search_items/<term>')
@login_required
def search_items(term):
    """Search for items."""
    try:
        items = ItemController.search_items(term)
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@item_bp.route('/categories')
@login_required
@permission_required('items')
def categories():
    """Render categories page."""
    return render_template('categories.html')


@item_bp.route('/get_categories')
@login_required
def get_categories():
    """Get all categories with section names."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.name, c.section_id, s.name as section_name
            FROM categories c
            LEFT JOIN sections s ON c.section_id = s.id
            WHERE ISNULL(c.active, 1) = 1
            ORDER BY s.name, c.name
        """)
        categories_data = cursor.fetchall()
        
        categories = [{
            'id': row[0],
            'name': row[1],
            'section_id': row[2],
            'section_name': row[3]
        } for row in categories_data]
        
        return jsonify(categories)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@item_bp.route('/save_category', methods=['POST'])
@login_required
@permission_required('items')
def save_category():
    """Create a new category."""
    try:
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO categories (name, section_id, active) 
            VALUES (?, ?, 1)
        """, [data['name'], data.get('section_id')])
        conn.commit()
        
        category_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
        return jsonify({'success': True, 'category_id': category_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@item_bp.route('/update_category/<int:category_id>', methods=['PUT'])
@login_required
@permission_required('items')
def update_category(category_id):
    """Update an existing category."""
    try:
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE categories 
            SET name = ?, section_id = ?
            WHERE id = ?
        """, [data['name'], data.get('section_id'), category_id])
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@item_bp.route('/delete_category/<int:category_id>', methods=['DELETE'])
@login_required
@permission_required('items')
def delete_category(category_id):
    """Delete a category."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Soft delete by setting active = 0
        cursor.execute("UPDATE categories SET active = 0 WHERE id = ?", [category_id])
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@item_bp.route('/companies')
@login_required
@permission_required('items')
def companies():
    """Render companies page."""
    return render_template('companies.html')


@item_bp.route('/get_companies')
@login_required
def get_companies():
    """Get all companies."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, phone FROM companies WHERE ISNULL(active, 1) = 1 ORDER BY name")
        companies_data = cursor.fetchall()
        
        companies = [{
            'id': row[0],
            'name': row[1],
            'phone': row[2] or ''
        } for row in companies_data]
        
        return jsonify(companies)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@item_bp.route('/save_company', methods=['POST'])
@login_required
@permission_required('items')
def save_company():
    """Create a new company."""
    try:
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO companies (name, phone, active) 
            VALUES (?, ?, 1)
        """, [data['name'], data.get('phone', '')])
        conn.commit()
        
        company_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
        return jsonify({'success': True, 'company_id': company_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@item_bp.route('/update_company/<int:company_id>', methods=['PUT'])
@login_required
@permission_required('items')
def update_company(company_id):
    """Update an existing company."""
    try:
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE companies 
            SET name = ?, phone = ?
            WHERE id = ?
        """, [data['name'], data.get('phone', ''), company_id])
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@item_bp.route('/delete_company/<int:company_id>', methods=['DELETE'])
@login_required
@permission_required('items')
def delete_company(company_id):
    """Delete a company."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Soft delete by setting active = 0
        cursor.execute("UPDATE companies SET active = 0 WHERE id = ?", [company_id])
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@item_bp.route('/get_sections')
@login_required
def get_sections():
    """Get all sections."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM sections WHERE ISNULL(active,1) = 1 ORDER BY name")
        sections_data = cursor.fetchall()
        
        sections = [{
            'id': row[0],
            'name': row[1]
        } for row in sections_data]
        
        return jsonify(sections)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@item_bp.route('/save_section', methods=['POST'])
@login_required
@permission_required('categories')
def save_section():
    """Create a new section."""
    try:
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO sections (name, active) VALUES (?, 1)",
            [data['name']]
        )
        conn.commit()
        
        section_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
        
        return jsonify({'success': True, 'section_id': section_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@item_bp.route('/update_section/<int:section_id>', methods=['PUT'])
@login_required
@permission_required('categories')
def update_section(section_id):
    """Update an existing section."""
    try:
        data = request.get_json()
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE sections SET name=? WHERE id=?",
            [data['name'], section_id]
        )
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@item_bp.route('/delete_section/<int:section_id>', methods=['DELETE'])
@login_required
@permission_required('categories')
def delete_section(section_id):
    """Delete a section."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Soft delete by setting active = 0
        cursor.execute("UPDATE sections SET active = 0 WHERE id = ?", [section_id])
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

