"""Sale model."""
from database.db import get_db
from datetime import datetime


class Sale:
    """Model for managing sales transactions."""
    
    @staticmethod
    def get_all(shift_id=None):
        """Get all sales, optionally filtered by shift."""
        conn = get_db()
        cursor = conn.cursor()
        
        if shift_id:
            cursor.execute("""
                SELECT * FROM daily_sales WHERE shift_id = ?
                ORDER BY created_at DESC
            """, [shift_id])
        else:
            cursor.execute("SELECT * FROM daily_sales ORDER BY created_at DESC")
        
        return cursor.fetchall()
    
    @staticmethod
    def get_by_id(sale_id):
        """Get sale by ID."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_sales WHERE id = ?", [sale_id])
        return cursor.fetchone()
    
    @staticmethod
    def get_items(sale_id):
        """Get items for a specific sale."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM daily_sale_items WHERE sale_id = ?
        """, [sale_id])
        return cursor.fetchall()
    
    @staticmethod
    def create(data, items):
        """Create a new sale with items."""
        conn = get_db()
        cursor = conn.cursor()
        
        # Insert sale record
        cursor.execute("""
            INSERT INTO daily_sales (
                sale_number, shift_id, total_amount, discount_amount,
                delivery_fee, final_amount, paid_amount, customer_name,
                customer_phone, address_line1, address_line2, address_line3
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            SELECT SCOPE_IDENTITY() AS id
        """, [
            data['sale_number'], data.get('shift_id'),
            data['total_amount'], data.get('discount_amount', 0),
            data.get('delivery_fee', 0), data['final_amount'],
            data.get('paid_amount', 0), data.get('customer_name', ''),
            data.get('customer_phone', ''), data.get('address_line1', ''),
            data.get('address_line2', ''), data.get('address_line3', '')
        ])
        result = cursor.fetchone()
        sale_id = int(result[0]) if result else None
        
        # Insert sale items
        for item in items:
            cursor.execute("""
                INSERT INTO daily_sale_items (
                    sale_id, barcode, item_name, quantity, unit_price, total_price
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, [
                sale_id, item['barcode'], item['item_name'],
                item['quantity'], item['unit_price'], item['total_price']
            ])
        
        conn.commit()
        return sale_id
    
    @staticmethod
    def process_return(sale_id, return_items):
        """Process a return for a sale."""
        conn = get_db()
        cursor = conn.cursor()
        
        # Implementation for returns
        # This would update inventory and create return records
        
        conn.commit()
        return True
