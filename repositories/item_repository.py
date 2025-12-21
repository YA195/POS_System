"""Item Repository - Data access layer for items."""
from repositories.base_repository import BaseRepository


class ItemRepository(BaseRepository):
    """Repository for item database operations."""
    
    def __init__(self):
        """Initialize item repository."""
        super().__init__('items')
    
    def get_all(self, include_deleted=False):
        """Get all items."""
        if include_deleted:
            query = """
                SELECT i.id, i.barcode, i.name, i.category_id, i.buy_price, i.sell_price, 
                       i.quantity, i.trader_id, i.active, i.barcode2, 
                       c.name as category_name, t.name as trader_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                LEFT JOIN traders t ON i.trader_id = t.id
                ORDER BY i.id DESC
            """
        else:
            query = """
                SELECT i.id, i.barcode, i.name, i.category_id, i.buy_price, i.sell_price, 
                       i.quantity, i.trader_id, i.active, i.barcode2,
                       c.name as category_name, t.name as trader_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                LEFT JOIN traders t ON i.trader_id = t.id
                WHERE ISNULL(i.active, 1) = 1
                ORDER BY i.id DESC
            """
        return self.execute_query(query)
    
    def get_by_id(self, item_id):
        """Get item by ID."""
        query = "SELECT * FROM items WHERE id = ?"
        return self.execute_query_one(query, [item_id])
    
    def get_by_barcode(self, barcode):
        """Get item by barcode or barcode2."""
        query = "SELECT * FROM items WHERE barcode = ? OR barcode2 = ?"
        return self.execute_query_one(query, [barcode, barcode])
    
    def get_by_category(self, category_id):
        """Get items by category."""
        query = "SELECT * FROM items WHERE category_id = ? AND ISNULL(active, 1) = 1"
        return self.execute_query(query, [category_id])
    
    def create(self, data):
        """Create new item."""
        query = """
            INSERT INTO items (barcode, name, category_id, buy_price, sell_price, 
                             quantity, trader_id, active, barcode2)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = [
            data['barcode'], data['name'], data.get('category_id'),
            data['buy_price'], data['sell_price'], data.get('quantity', 0),
            data.get('trader_id'), data.get('active', 1), data.get('barcode2')
        ]
        return self.create(query, params)
    
    def update(self, item_id, data):
        """Update item."""
        query = """
            UPDATE items SET barcode = ?, name = ?, category_id = ?, 
                           buy_price = ?, sell_price = ?, quantity = ?, 
                           trader_id = ?, active = ?, barcode2 = ?
            WHERE id = ?
        """
        params = [
            data['barcode'], data['name'], data.get('category_id'),
            data['buy_price'], data['sell_price'], data.get('quantity', 0),
            data.get('trader_id'), data.get('active', 1), data.get('barcode2'),
            item_id
        ]
        return self.update(query, params)
    
    def delete(self, item_id):
        """Soft delete item."""
        query = "UPDATE items SET active = 0 WHERE id = ?"
        return self.update(query, [item_id])
