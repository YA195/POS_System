"""Item controller for business logic."""
from models.item import Item
from utils.logger import log_activity


class ItemController:
    """Controller for item-related business logic."""
    
    @staticmethod
    def get_all_items(include_deleted=False):
        """Get all items with additional processing."""
        items = Item.get_all(include_deleted)
        return [ItemController._format_item(item) for item in items]
    
    @staticmethod
    def get_item(item_id):
        """Get a single item."""
        item = Item.get_by_id(item_id)
        return ItemController._format_item(item) if item else None
    
    @staticmethod
    def create_item(data):
        """Create a new item with validation."""
        # Validate required fields
        required_fields = ['barcode', 'name', 'buy_price', 'sell_price']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValueError(f"Missing required field: {field}")
        
        # Check if barcode already exists
        if not data.get('id'):
            existing = Item.get_by_barcode(data['barcode'])
            if existing:
                raise ValueError(f"Barcode {data['barcode']} already exists")
        
        # Create item
        item_id = Item.create(data)
        
        # Log activity
        log_activity('CREATE', f"Created item: {data['name']}", 'items', item_id)
        
        return item_id
    
    @staticmethod
    def update_item(item_id, data):
        """Update an existing item."""
        # Check if item exists
        item = Item.get_by_id(item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")
        
        # Update item
        Item.update(item_id, data)
        
        # Log activity
        log_activity('UPDATE', f"Updated item: {data.get('name', 'Unknown')}", 'items', item_id)
        
        return True
    
    @staticmethod
    def delete_item(item_id):
        """Delete an item."""
        item = Item.get_by_id(item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")
        
        Item.delete(item_id)
        
        # Log activity
        log_activity('DELETE', f"Deleted item ID: {item_id}", 'items', item_id)
        
        return True
    
    @staticmethod
    def restore_item(item_id):
        """Restore a deleted item."""
        Item.restore(item_id)
        log_activity('RESTORE', f"Restored item ID: {item_id}", 'items', item_id)
        return True
    
    @staticmethod
    def search_items(term):
        """Search for items."""
        return Item.search(term)
    
    @staticmethod
    def _format_item(item):
        """Format item data for API response."""
        if not item:
            return None
        
        # Schema: id, barcode, name, category_id, buy_price, sell_price, quantity, trader_id, active, barcode2, category_name, trader_name
        return {
            'id': item[0] if len(item) > 0 else None,
            'barcode': item[1] if len(item) > 1 else '',
            'name': item[2] if len(item) > 2 else '',
            'category_id': item[3] if len(item) > 3 else None,
            'buy_price': float(item[4]) if len(item) > 4 and item[4] else 0,
            'sell_price': float(item[5]) if len(item) > 5 and item[5] else 0,
            'quantity': item[6] if len(item) > 6 else 0,
            'trader_id': item[7] if len(item) > 7 else None,
            'active': item[8] if len(item) > 8 else 1,
            'barcode2': item[9] if len(item) > 9 else '',
            'category_name': item[10] if len(item) > 10 else '',
            'trader_name': item[11] if len(item) > 11 else ''
        }
