"""Report controller for business logic."""
from database.db import get_db
from datetime import datetime, timedelta


class ReportController:
    """Controller for generating reports."""
    
    @staticmethod
    def get_sales_report(start_date=None, end_date=None):
        """Generate sales report for date range."""
        conn = get_db()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                DATE(created_at) as sale_date,
                COUNT(*) as total_sales,
                SUM(total_amount) as total_revenue,
                SUM(discount_amount) as total_discounts,
                SUM(final_amount) as net_revenue
            FROM daily_sales
        """
        
        params = []
        if start_date and end_date:
            query += " WHERE DATE(created_at) BETWEEN ? AND ?"
            params = [start_date, end_date]
        
        query += " GROUP BY DATE(created_at) ORDER BY sale_date DESC"
        
        cursor.execute(query, params)
        return cursor.fetchall()
    
    @staticmethod
    def get_inventory_report():
        """Generate inventory status report."""
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                i.id, i.barcode, i.item_name, i.quantity,
                i.cost_price, i.selling_price,
                c.category_name, co.company_name,
                (i.quantity * i.cost_price) as total_cost_value,
                (i.quantity * i.selling_price) as total_selling_value
            FROM items i
            LEFT JOIN categories c ON i.category_id = c.id
            LEFT JOIN companies co ON i.company_id = co.id
            WHERE i.is_deleted = 0
            ORDER BY i.item_name
        """)
        
        return cursor.fetchall()
    
    @staticmethod
    def get_low_stock_items(threshold=10):
        """Get items with low stock."""
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM items 
            WHERE quantity <= ? AND is_deleted = 0
            ORDER BY quantity ASC
        """, [threshold])
        
        return cursor.fetchall()
    
    @staticmethod
    def get_profit_report(start_date=None, end_date=None):
        """Calculate profit for date range."""
        conn = get_db()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                SUM(si.quantity * (si.unit_price - i.cost_price)) as total_profit
            FROM daily_sale_items si
            INNER JOIN items i ON si.barcode = i.barcode
            INNER JOIN daily_sales s ON si.sale_id = s.id
        """
        
        params = []
        if start_date and end_date:
            query += " WHERE DATE(s.created_at) BETWEEN ? AND ?"
            params = [start_date, end_date]
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        
        return result[0] if result and result[0] else 0
    
    @staticmethod
    def get_item_movement_report(item_id=None, start_date=None, end_date=None):
        """Generate item movement report."""
        conn = get_db()
        cursor = conn.cursor()
        
        # Sales movements
        sales_query = """
            SELECT 
                'SALE' as movement_type,
                s.created_at,
                si.barcode,
                si.item_name,
                -si.quantity as quantity_change,
                si.total_price as amount
            FROM daily_sale_items si
            INNER JOIN daily_sales s ON si.sale_id = s.id
        """
        
        # Invoice movements
        invoice_query = """
            SELECT 
                'INVOICE' as movement_type,
                inv.created_at,
                ii.barcode,
                ii.item_name,
                ii.quantity as quantity_change,
                ii.total_price as amount
            FROM invoice_items ii
            INNER JOIN invoices inv ON ii.invoice_id = inv.id
        """
        
        params = []
        where_clause = ""
        
        if item_id:
            where_clause = " WHERE si.barcode = (SELECT barcode FROM items WHERE id = ?)"
            params.append(item_id)
        
        if start_date and end_date:
            if where_clause:
                where_clause += " AND DATE(s.created_at) BETWEEN ? AND ?"
            else:
                where_clause = " WHERE DATE(s.created_at) BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        
        full_query = f"""
            {sales_query}{where_clause}
            UNION ALL
            {invoice_query}{where_clause.replace('s.', 'inv.')}
            ORDER BY created_at DESC
        """
        
        cursor.execute(full_query, params * 2 if params else [])
        return cursor.fetchall()
    
    @staticmethod
    def get_supplier_balance_report():
        """Generate supplier balance report."""
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                t.id, t.trader_name, t.phone, t.balance,
                COUNT(i.id) as invoice_count,
                COALESCE(SUM(i.total_amount), 0) as total_invoiced,
                COALESCE(SUM(i.paid_amount), 0) as total_paid
            FROM traders t
            LEFT JOIN invoices i ON t.id = i.trader_id
            WHERE t.is_deleted = 0
            GROUP BY t.id, t.trader_name, t.phone, t.balance
            HAVING t.balance > 0
            ORDER BY t.balance DESC
        """)
        
        return cursor.fetchall()
