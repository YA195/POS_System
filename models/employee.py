"""Employee model."""
from database.db import get_db


class Employee:
    """Model for managing employees."""
    
    @staticmethod
    def get_all():
        """Get all employees."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employees ORDER BY created_at DESC")
        return cursor.fetchall()
    
    @staticmethod
    def get_by_id(employee_id):
        """Get employee by ID."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employees WHERE id = ?", [employee_id])
        return cursor.fetchone()
    
    @staticmethod
    def create(data):
        """Create a new employee."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO employees (name, phone, address, salary, is_active)
            VALUES (?, ?, ?, ?, ?);
            SELECT SCOPE_IDENTITY() AS id
        """, [
            data['name'], data.get('phone', ''),
            data.get('address', ''), data.get('salary', 0),
            data.get('is_active', 1)
        ])
        result = cursor.fetchone()
        conn.commit()
        return int(result[0]) if result else None
    
    @staticmethod
    def update(employee_id, data):
        """Update an existing employee."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE employees 
            SET name = ?, phone = ?, address = ?, salary = ?, is_active = ?
            WHERE id = ?
        """, [
            data['name'], data.get('phone', ''),
            data.get('address', ''), data.get('salary', 0),
            data.get('is_active', 1), employee_id
        ])
        conn.commit()
        return cursor.rowcount
    
    @staticmethod
    def toggle_status(employee_id):
        """Toggle employee active status."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE employees 
            SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
            WHERE id = ?
        """, [employee_id])
        conn.commit()
        return cursor.rowcount
