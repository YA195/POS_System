"""Item model for inventory management."""
from repositories.item_repository import ItemRepository


class Item:
    """Model for managing inventory items."""
    
    def __init__(self):
        """Initialize with repository."""
        self.repository = ItemRepository()
    
    def get_all(self, include_deleted=False):
        """Get all items from database."""
        return self.repository.get_all(include_deleted)
    
    def get_by_id(self, item_id):
        """Get item by ID."""
        return self.repository.get_by_id(item_id)
    
    def get_by_barcode(self, barcode):
        """Get item by barcode or barcode2."""
        return self.repository.get_by_barcode(barcode)
    
    def get_by_category(self, category_id):
        """Get items by category."""
        return self.repository.get_by_category(category_id)
    
    def create(self, data):
        """Create a new item."""
        return self.repository.create(data)
    
    def update(self, item_id, data):
        """Update an existing item."""
        return self.repository.update(item_id, data)
    
    def delete(self, item_id, soft_delete=True):
        """Delete an item (soft or hard delete)."""
        if soft_delete:
            return self.repository.delete(item_id)
        else:
            return self.repository.delete(item_id)
    
    def search(self, term):
        """Search items by name or barcode."""
        conn = self.repository.get_connection()
        cursor = conn.cursor()
        search_term = f'%{term}%'
        cursor.execute("""
            SELECT * FROM items 
            WHERE (name LIKE ? OR barcode LIKE ?)
            AND ISNULL(active, 1) = 1
        """, [search_term, search_term])
        return cursor.fetchall()

