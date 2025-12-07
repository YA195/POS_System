"""Invoice controller for business logic."""
from models.invoice import Invoice
from models.trader import Trader
from utils.logger import log_activity
from database.db import get_db


class InvoiceController:
    """Controller for invoice-related business logic."""
    
    @staticmethod
    def create_invoice(invoice_data, items):
        """Create a new invoice with inventory updates."""
        # Validate trader exists
        trader = Trader.get_by_id(invoice_data['trader_id'])
        if not trader:
            raise ValueError(f"Trader {invoice_data['trader_id']} not found")
        
        # Create invoice
        invoice_id = Invoice.create(invoice_data, items)
        
        # Update trader balance
        conn = get_db()
        cursor = conn.cursor()
        remaining = invoice_data['total_amount'] - invoice_data.get('paid_amount', 0)
        cursor.execute("""
            UPDATE traders 
            SET balance = balance + ? 
            WHERE id = ?
        """, [remaining, invoice_data['trader_id']])
        conn.commit()
        
        # Log activity
        log_activity('CREATE', f"Created invoice for trader {trader[1]}", 'invoices', invoice_id)
        
        return invoice_id
    
    @staticmethod
    def get_invoice_details(invoice_id):
        """Get complete invoice details including items."""
        invoice = Invoice.get_by_id(invoice_id)
        if not invoice:
            return None
        
        items = Invoice.get_items(invoice_id)
        
        return {
            'invoice': invoice,
            'items': items
        }
    
    @staticmethod
    def process_payment(invoice_id, amount):
        """Process a payment for an invoice."""
        invoice = Invoice.get_by_id(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        # Update invoice
        Invoice.process_payment(invoice_id, amount)
        
        # Update trader balance
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE traders 
            SET balance = balance - ? 
            WHERE id = ?
        """, [amount, invoice[1]])  # Assuming column 1 is trader_id
        conn.commit()
        
        # Log activity
        log_activity('PAYMENT', f"Payment of {amount} for invoice {invoice_id}", 'invoices', invoice_id)
        
        return True
    
    @staticmethod
    def get_supplier_invoices(trader_id):
        """Get all invoices for a specific supplier."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM invoices 
            WHERE trader_id = ? 
            ORDER BY created_at DESC
        """, [trader_id])
        return cursor.fetchall()
