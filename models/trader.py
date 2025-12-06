"""Trader/Supplier model."""
from database.db import get_db


class Trader:
    """Model for managing traders/suppliers."""
    
    @staticmethod
    def get_all(include_deleted=False):
        """Get all traders from database."""
        conn = get_db()
        cursor = conn.cursor()
        
        if include_deleted:
            cursor.execute("SELECT * FROM traders")
        else:
            cursor.execute("SELECT * FROM traders WHERE is_deleted = 0")
        
        return cursor.fetchall()
    
    @staticmethod
    def get_by_id(trader_id):
        """Get trader by ID."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM traders WHERE id = ?", [trader_id])
        return cursor.fetchone()
    
    @staticmethod
    def create(data):
        """Create a new trader."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO traders (trader_name, phone, address, balance)
            VALUES (?, ?, ?, ?);
            SELECT SCOPE_IDENTITY() AS id
        """, [
            data['trader_name'], data.get('phone', ''),
            data.get('address', ''), data.get('balance', 0.0)
        ])
        result = cursor.fetchone()
        conn.commit()
        return int(result[0]) if result else None
    
    @staticmethod
    def update(trader_id, data):
        """Update an existing trader."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE traders SET
                trader_name = ?, phone = ?, address = ?, balance = ?
            WHERE id = ?
        """, [
            data['trader_name'], data.get('phone', ''),
            data.get('address', ''), data.get('balance', 0.0),
            trader_id
        ])
        conn.commit()
        return cursor.rowcount
    
    @staticmethod
    def delete(trader_id, soft_delete=True):
        """Delete a trader (soft or hard delete)."""
        conn = get_db()
        cursor = conn.cursor()
        
        if soft_delete:
            cursor.execute("UPDATE traders SET is_deleted = 1 WHERE id = ?", [trader_id])
        else:
            cursor.execute("DELETE FROM traders WHERE id = ?", [trader_id])
        
        conn.commit()
        return cursor.rowcount
    
    @staticmethod
    def restore(trader_id):
        """Restore a soft-deleted trader."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE traders SET is_deleted = 0 WHERE id = ?", [trader_id])
        conn.commit()
        return cursor.rowcount
