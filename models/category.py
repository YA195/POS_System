"""Category model."""
from database.db import get_db


class Category:
    """Model for managing product categories."""
    
    @staticmethod
    def get_all(include_deleted=False):
        """Get all categories from database."""
        conn = get_db()
        cursor = conn.cursor()
        
        if include_deleted:
            cursor.execute("SELECT * FROM categories")
        else:
            cursor.execute("SELECT * FROM categories WHERE is_deleted = 0")
        
        return cursor.fetchall()
    
    @staticmethod
    def get_by_id(category_id):
        """Get category by ID."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories WHERE id = ?", [category_id])
        return cursor.fetchone()
    
    @staticmethod
    def create(data):
        """Create a new category."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO categories (category_name)
            VALUES (?);
            SELECT SCOPE_IDENTITY() AS id
        """, [data['category_name']])
        result = cursor.fetchone()
        conn.commit()
        return int(result[0]) if result else None
    
    @staticmethod
    def update(category_id, data):
        """Update an existing category."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE categories SET category_name = ? WHERE id = ?
        """, [data['category_name'], category_id])
        conn.commit()
        return cursor.rowcount
    
    @staticmethod
    def delete(category_id, soft_delete=True):
        """Delete a category (soft or hard delete)."""
        conn = get_db()
        cursor = conn.cursor()
        
        if soft_delete:
            cursor.execute("UPDATE categories SET is_deleted = 1 WHERE id = ?", [category_id])
        else:
            cursor.execute("DELETE FROM categories WHERE id = ?", [category_id])
        
        conn.commit()
        return cursor.rowcount
    
    @staticmethod
    def restore(category_id):
        """Restore a soft-deleted category."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE categories SET is_deleted = 0 WHERE id = ?", [category_id])
        conn.commit()
        return cursor.rowcount
