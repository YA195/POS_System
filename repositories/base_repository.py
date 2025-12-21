"""Base Repository class for common database operations."""
from database.db import get_db


class BaseRepository:
    """Base repository with common CRUD operations."""
    
    def __init__(self, table_name):
        """Initialize repository with table name."""
        self.table_name = table_name
    
    def get_connection(self):
        """Get database connection."""
        return get_db()
    
    def find_all(self):
        """Find all records in table."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {self.table_name}")
        return cursor.fetchall()
    
    def find_by_id(self, record_id):
        """Find record by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {self.table_name} WHERE id = ?", [record_id])
        return cursor.fetchone()
    
    def execute_query(self, query, params=None):
        """Execute custom query and return results."""
        conn = self.get_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchall()
    
    def execute_query_one(self, query, params=None):
        """Execute custom query and return single result."""
        conn = self.get_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchone()
    
    def create(self, query, params):
        """Create new record."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount
    
    def update(self, query, params):
        """Update existing record."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount
    
    def delete(self, query, params):
        """Delete record."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount
