"""Item management views."""
from flask import Blueprint, render_template, request, jsonify
from controllers.item_controller import ItemController
from models.category import Category
from models.company import Company
from utils.auth import login_required, permission_required

item_bp = Blueprint('items', __name__)


@item_bp.route('/items')
@login_required
@permission_required('items')
def items():
    """Render items page."""
    return render_template('Items.html')


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


@item_bp.route('/save_item', methods=['POST'])
@login_required
@permission_required('items')
def save_item():
    """Create a new item."""
    try:
        data = request.get_json()
        item_id = ItemController.create_item(data)
        return jsonify({'success': True, 'item_id': item_id})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
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
    """Get all categories."""
    try:
        categories = Category.get_all()
        return jsonify({'success': True, 'categories': categories})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@item_bp.route('/save_category', methods=['POST'])
@login_required
@permission_required('items')
def save_category():
    """Create a new category."""
    try:
        data = request.get_json()
        category_id = Category.create(data)
        return jsonify({'success': True, 'category_id': category_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
        companies = Company.get_all()
        return jsonify({'success': True, 'companies': companies})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
