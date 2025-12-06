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
                SELECT i.*, c.category_name, co.company_name, s.section_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                LEFT JOIN companies co ON i.company_id = co.id
                LEFT JOIN sections s ON i.section_id = s.id
            """)
        else:
            cursor.execute("""
                SELECT i.*, c.category_name, co.company_name, s.section_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                LEFT JOIN companies co ON i.company_id = co.id
                LEFT JOIN sections s ON i.section_id = s.id
                WHERE i.is_deleted = 0
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
        """Get item by barcode."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM items 
            WHERE barcode = ? OR additional_barcodes LIKE ?
        """, [barcode, f'%{barcode}%'])
        return cursor.fetchone()
    
    @staticmethod
    def create(data):
        """Create a new item."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO items (
                barcode, item_name, category_id, company_id, section_id,
                quantity, cost_price, selling_price, quick_sale
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            SELECT SCOPE_IDENTITY() AS id
        """, [
            data['barcode'], data['item_name'], data.get('category_id'),
            data.get('company_id'), data.get('section_id'), data.get('quantity', 0),
            data['cost_price'], data['selling_price'], data.get('quick_sale', 0)
        ])
        result = cursor.fetchone()
        conn.commit()
        return int(result[0]) if result else None
    
    @staticmethod
    def update(item_id, data):
        """Update an existing item."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE items SET
                barcode = ?, item_name = ?, category_id = ?, company_id = ?,
                section_id = ?, quantity = ?, cost_price = ?, selling_price = ?,
                quick_sale = ?
            WHERE id = ?
        """, [
            data['barcode'], data['item_name'], data.get('category_id'),
            data.get('company_id'), data.get('section_id'), data['quantity'],
            data['cost_price'], data['selling_price'], data.get('quick_sale', 0),
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
            cursor.execute("UPDATE items SET is_deleted = 1 WHERE id = ?", [item_id])
        else:
            cursor.execute("DELETE FROM items WHERE id = ?", [item_id])
        
        conn.commit()
        return cursor.rowcount
    
    @staticmethod
    def restore(item_id):
        """Restore a soft-deleted item."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE items SET is_deleted = 0 WHERE id = ?", [item_id])
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
            WHERE (item_name LIKE ? OR barcode LIKE ?)
            AND is_deleted = 0
        """, [search_term, search_term])
        return cursor.fetchall()
