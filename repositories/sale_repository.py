"""Sale Repository - Data access layer for sales."""
from repositories.base_repository import BaseRepository


class SaleRepository(BaseRepository):
    """Repository for sale database operations."""
    
    def __init__(self):
        """Initialize sale repository."""
        super().__init__('daily_sales')
    
    def get_all(self, shift_id=None):
        """Get all sales."""
        if shift_id:
            query = "SELECT * FROM daily_sales WHERE shift_id = ? ORDER BY created_at DESC"
            return self.execute_query(query, [shift_id])
        else:
            query = "SELECT * FROM daily_sales ORDER BY created_at DESC"
            return self.execute_query(query)
    
    def get_by_id(self, sale_id):
        """Get sale by ID."""
        query = "SELECT * FROM daily_sales WHERE id = ?"
        return self.execute_query_one(query, [sale_id])
    
    def get_items(self, sale_id):
        """Get items for a specific sale."""
        query = "SELECT * FROM daily_sale_items WHERE sale_id = ?"
        return self.execute_query(query, [sale_id])
    
    def get_by_shift(self, shift_id):
        """Get sales for a shift."""
        query = "SELECT * FROM daily_sales WHERE shift_id = ? ORDER BY created_at DESC"
        return self.execute_query(query, [shift_id])
    
    def create(self, data):
        """Create new sale."""
        query = """
            INSERT INTO daily_sales (
                sale_number, shift_id, total_amount, subtotal, discount_amount,
                delivery_fee, final_amount, payment_method, paid_amount, residual_amount,
                customer_name, customer_phone, address_line1, address_line2, address_line3,
                cash_box_id, user_id, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = [
            data['sale_number'], data.get('shift_id'), data['total_amount'],
            data['subtotal'], data.get('discount_amount', 0), data.get('delivery_fee', 0),
            data['final_amount'], data['payment_method'], data.get('paid_amount', 0),
            data.get('residual_amount', 0), data.get('customer_name'), 
            data.get('customer_phone'), data.get('address_line1'),
            data.get('address_line2'), data.get('address_line3'),
            data.get('cash_box_id'), data.get('user_id'), 'completed'
        ]
        return self.create(query, params)
    
    def update(self, sale_id, data):
        """Update sale."""
        query = """
            UPDATE daily_sales 
            SET sale_number = ?, total_amount = ?, payment_method = ?, status = ?
            WHERE id = ?
        """
        params = [
            data.get('sale_number'), data.get('total_amount'),
            data.get('payment_method'), data.get('status', 'completed'), sale_id
        ]
        return self.update(query, params)
    
    def delete(self, sale_id):
        """Delete sale."""
        query = "DELETE FROM daily_sales WHERE id = ?"
        return self.delete(query, [sale_id])
