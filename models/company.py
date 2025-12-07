"""Company model."""
from database.db import get_db


class Company:
    """Model for managing companies/manufacturers."""
    
    @staticmethod
    def get_all(include_deleted=False):
        """Get all companies from database."""
        conn = get_db()
        cursor = conn.cursor()
        
        if include_deleted:
            cursor.execute("SELECT * FROM companies")
        else:
            cursor.execute("SELECT * FROM companies WHERE is_deleted = 0")
        
        return cursor.fetchall()
    
    @staticmethod
    def get_by_id(company_id):
        """Get company by ID."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM companies WHERE id = ?", [company_id])
        return cursor.fetchone()
    
    @staticmethod
    def create(data):
        """Create a new company."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO companies (company_name)
            VALUES (?);
            SELECT SCOPE_IDENTITY() AS id
        """, [data['company_name']])
        result = cursor.fetchone()
        conn.commit()
        return int(result[0]) if result else None
    
    @staticmethod
    def update(company_id, data):
        """Update an existing company."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE companies SET company_name = ? WHERE id = ?
        """, [data['company_name'], company_id])
        conn.commit()
        return cursor.rowcount
    
    @staticmethod
    def delete(company_id, soft_delete=True):
        """Delete a company (soft or hard delete)."""
        conn = get_db()
        cursor = conn.cursor()
        
        if soft_delete:
            cursor.execute("UPDATE companies SET is_deleted = 1 WHERE id = ?", [company_id])
        else:
            cursor.execute("DELETE FROM companies WHERE id = ?", [company_id])
        
        conn.commit()
        return cursor.rowcount
    
    @staticmethod
    def restore(company_id):
        """Restore a soft-deleted company."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE companies SET is_deleted = 0 WHERE id = ?", [company_id])
        conn.commit()
        return cursor.rowcount
