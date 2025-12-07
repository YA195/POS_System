"""Item model for inventory management."""
from database.db import get_db


class Item:
    """Model for managing inventory items."""
    
    @staticmethod
    def get_all(include_deleted=False):
        """Get all items from database."""
        conn = get_db()
        cursor = conn.cursor()
        
        if include_deleted:
            cursor.execute("""
                SELECT i.id, i.barcode, i.name, i.category_id, i.buy_price, i.sell_price, 
                       i.quantity, i.trader_id, i.active, i.barcode2, 
                       c.name as category_name, t.name as trader_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                LEFT JOIN traders t ON i.trader_id = t.id
                ORDER BY i.id DESC
            """)
        else:
            cursor.execute("""
                SELECT i.id, i.barcode, i.name, i.category_id, i.buy_price, i.sell_price, 
                       i.quantity, i.trader_id, i.active, i.barcode2,
                       c.name as category_name, t.name as trader_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                LEFT JOIN traders t ON i.trader_id = t.id
                WHERE ISNULL(i.active, 1) = 1
                ORDER BY i.id DESC
            """)
        
        return cursor.fetchall()
    
    @staticmethod
    def get_by_id(item_id):
        """Get item by ID."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items WHERE id = ?", [item_id])
        return cursor.fetchone()
    
    @staticmethod
    def get_by_barcode(barcode):
        """Get item by barcode or barcode2."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM items 
            WHERE barcode = ? OR barcode2 LIKE ?
        """, [barcode, f'%{barcode}%'])
        return cursor.fetchone()
    
    @staticmethod
    def create(data):
        """Create a new item."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO items (
                barcode, name, category_id, trader_id, barcode2,
                quantity, buy_price, sell_price, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, [
            data.get('barcode'),
            data.get('name') or data.get('item_name'),
            data.get('category_id'),
            data.get('trader_id') or data.get('company_id'),
            data.get('barcode2', ''),
            data.get('quantity', 0),
            data.get('buy_price') or data.get('cost_price'),
            data.get('sell_price') or data.get('selling_price')
        ])
        conn.commit()
        
        # Get the last inserted ID
        cursor.execute("SELECT @@IDENTITY AS id")
        result = cursor.fetchone()
        return int(result[0]) if result else None
    
    @staticmethod
    def update(item_id, data):
        """Update an existing item."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE items SET
                barcode = ?, name = ?, category_id = ?, trader_id = ?,
                barcode2 = ?, quantity = ?, buy_price = ?, sell_price = ?
            WHERE id = ?
        """, [
            data.get('barcode'),
            data.get('name') or data.get('item_name'),
            data.get('category_id'),
            data.get('trader_id') or data.get('company_id'),
            data.get('barcode2', ''),
            data.get('quantity', 0),
            data.get('buy_price') or data.get('cost_price'),
            data.get('sell_price') or data.get('selling_price'),
            item_id
        ])
        conn.commit()
        return cursor.rowcount
    
    @staticmethod
    def delete(item_id, soft_delete=True):
        """Delete an item (soft or hard delete)."""
        conn = get_db()
        cursor = conn.cursor()
        
        if soft_delete:
            cursor.execute("UPDATE items SET active = 0 WHERE id = ?", [item_id])
        else:
            cursor.execute("DELETE FROM items WHERE id = ?", [item_id])
        
        conn.commit()
        return cursor.rowcount
    
    @staticmethod
    def restore(item_id):
        """Restore a soft-deleted item."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE items SET active = 1 WHERE id = ?", [item_id])
        conn.commit()
        return cursor.rowcount
    
    @staticmethod
    def search(term):
        """Search items by name or barcode."""
        conn = get_db()
        cursor = conn.cursor()
        search_term = f'%{term}%'
        cursor.execute("""
            SELECT * FROM items 
            WHERE (name LIKE ? OR barcode LIKE ?)
            AND ISNULL(active, 1) = 1
        """, [search_term, search_term])
        return cursor.fetchall()
