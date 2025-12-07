"""Shift model."""
from database.db import get_db
from datetime import datetime


class Shift:
    """Model for managing work shifts."""
    
    @staticmethod
    def get_all():
        """Get all shifts."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, u.username 
            FROM shifts s
            LEFT JOIN users u ON s.user_id = u.id
            ORDER BY s.start_time DESC
        """)
        return cursor.fetchall()
    
    @staticmethod
    def get_by_id(shift_id):
        """Get shift by ID."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shifts WHERE id = ?", [shift_id])
        return cursor.fetchone()
    
    @staticmethod
    def get_active():
        """Get the currently active shift."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP 1 * FROM shifts 
            WHERE end_time IS NULL 
            ORDER BY start_time DESC
        """)
        return cursor.fetchone()
    
    @staticmethod
    def create(user_id, cashier_name, opening_balance=0):
        """Create a new shift."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO shifts (user_id, cashier_name, start_time, status)
            VALUES (?, ?, GETDATE(), 'active')
        """, [user_id, cashier_name])
        conn.commit()
        
        # Get the last inserted ID
        cursor.execute("SELECT @@IDENTITY AS id")
        result = cursor.fetchone()
        return int(result[0]) if result else None
    
    @staticmethod
    def close(shift_id, closing_data):
        """Close a shift."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE shifts 
            SET end_time = GETDATE(),
                closing_balance = ?,
                total_sales = ?,
                total_expenses = ?
            WHERE id = ?
        """, [
            closing_data.get('closing_balance', 0),
            closing_data.get('total_sales', 0),
            closing_data.get('total_expenses', 0),
            shift_id
        ])
        conn.commit()
        return cursor.rowcount
    
    @staticmethod
    def get_summary(shift_id):
        """Get summary data for a shift."""
        conn = get_db()
        cursor = conn.cursor()
        
        # Get shift details
        cursor.execute("SELECT * FROM shifts WHERE id = ?", [shift_id])
        shift = cursor.fetchone()
        
        # Get sales count and total
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(final_amount), 0)
            FROM daily_sales WHERE shift_id = ?
        """, [shift_id])
        sales_data = cursor.fetchone()
        
        # Get expenses total
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses WHERE shift_id = ?
        """, [shift_id])
        expenses_total = cursor.fetchone()[0]
        
        return {
            'shift': shift,
            'sales_count': sales_data[0],
            'sales_total': sales_data[1],
            'expenses_total': expenses_total
        }
