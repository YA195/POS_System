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
        required_fields = ['barcode', 'item_name', 'cost_price', 'selling_price']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValueError(f"Missing required field: {field}")
        
        # Check if barcode already exists
        existing = Item.get_by_barcode(data['barcode'])
        if existing:
            raise ValueError(f"Barcode {data['barcode']} already exists")
        
        # Create item
        item_id = Item.create(data)
        
        # Log activity
        log_activity('CREATE', f"Created item: {data['item_name']}", 'items', item_id)
        
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
        log_activity('UPDATE', f"Updated item: {data.get('item_name', 'Unknown')}", 'items', item_id)
        
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
        
        # Convert tuple to dict based on your schema
        return {
            'id': item[0],
            'barcode': item[1],
            'item_name': item[2],
            # Add other fields as needed
        }
