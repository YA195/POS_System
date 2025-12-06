"""Invoice model."""
from database.db import get_db


class Invoice:
    """Model for managing purchase invoices."""
    
    @staticmethod
    def get_all():
        """Get all invoices."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT i.*, t.trader_name 
            FROM invoices i
            LEFT JOIN traders t ON i.trader_id = t.id
            ORDER BY i.created_at DESC
        """)
        return cursor.fetchall()
    
    @staticmethod
    def get_by_id(invoice_id):
        """Get invoice by ID."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM invoices WHERE id = ?", [invoice_id])
        return cursor.fetchone()
    
    @staticmethod
    def get_items(invoice_id):
        """Get items for a specific invoice."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM invoice_items WHERE invoice_id = ?
        """, [invoice_id])
        return cursor.fetchall()
    
    @staticmethod
    def create(data, items):
        """Create a new invoice with items."""
        conn = get_db()
        cursor = conn.cursor()
        
        # Insert invoice record
        cursor.execute("""
            INSERT INTO invoices (
                trader_id, total_amount, paid_amount, remaining_balance, created_at
            ) VALUES (?, ?, ?, ?, GETDATE());
            SELECT SCOPE_IDENTITY() AS id
        """, [
            data['trader_id'], data['total_amount'],
            data.get('paid_amount', 0),
            data['total_amount'] - data.get('paid_amount', 0)
        ])
        result = cursor.fetchone()
        invoice_id = int(result[0]) if result else None
        
        # Insert invoice items and update inventory
        for item in items:
            cursor.execute("""
                INSERT INTO invoice_items (
                    invoice_id, barcode, item_name, quantity, cost_price, total_price
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, [
                invoice_id, item['barcode'], item['item_name'],
                item['quantity'], item['cost_price'], item['total_price']
            ])
            
            # Update item quantity in inventory
            cursor.execute("""
                UPDATE items SET quantity = quantity + ? WHERE barcode = ?
            """, [item['quantity'], item['barcode']])
        
        conn.commit()
        return invoice_id
    
    @staticmethod
    def process_payment(invoice_id, amount):
        """Process a payment for an invoice."""
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE invoices 
            SET paid_amount = paid_amount + ?,
                remaining_balance = remaining_balance - ?
            WHERE id = ?
        """, [amount, amount, invoice_id])
        
        conn.commit()
        return cursor.rowcount
