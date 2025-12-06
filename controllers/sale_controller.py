"""Sale controller for business logic."""
from models.sale import Sale
from models.item import Item
from utils.logger import log_activity
from database.db import get_db


class SaleController:
    """Controller for sale-related business logic."""
    
    @staticmethod
    def create_sale(sale_data, items):
        """Create a new sale with inventory updates."""
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Validate items have sufficient quantity
            for item in items:
                db_item = Item.get_by_barcode(item['barcode'])
                if not db_item:
                    raise ValueError(f"Item with barcode {item['barcode']} not found")
                
                # Check quantity
                if db_item[5] < item['quantity']:  # Assuming column 5 is quantity
                    raise ValueError(f"Insufficient quantity for {item['item_name']}")
            
            # Create sale
            sale_id = Sale.create(sale_data, items)
            
            # Update inventory
            for item in items:
                cursor.execute("""
                    UPDATE items 
                    SET quantity = quantity - ? 
                    WHERE barcode = ?
                """, [item['quantity'], item['barcode']])
            
            conn.commit()
            
            # Log activity
            log_activity('CREATE', f"Created sale #{sale_data['sale_number']}", 'daily_sales', sale_id)
            
            return sale_id
            
        except Exception as e:
            conn.rollback()
            raise e
    
    @staticmethod
    def get_sale_details(sale_id):
        """Get complete sale details including items."""
        sale = Sale.get_by_id(sale_id)
        if not sale:
            return None
        
        items = Sale.get_items(sale_id)
        
        return {
            'sale': sale,
            'items': items
        }
    
    @staticmethod
    def process_return(sale_id, return_items):
        """Process a return for a sale."""
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Validate sale exists
            sale = Sale.get_by_id(sale_id)
            if not sale:
                raise ValueError(f"Sale {sale_id} not found")
            
            # Process each returned item
            for item in return_items:
                # Update inventory - add back returned quantity
                cursor.execute("""
                    UPDATE items 
                    SET quantity = quantity + ? 
                    WHERE barcode = ?
                """, [item['quantity'], item['barcode']])
                
                # Create return record
                cursor.execute("""
                    INSERT INTO sale_returns (
                        sale_id, barcode, item_name, quantity, 
                        unit_price, total_price, return_date
                    ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """, [
                    sale_id, item['barcode'], item['item_name'],
                    item['quantity'], item['unit_price'],
                    item['quantity'] * item['unit_price']
                ])
            
            conn.commit()
            
            # Log activity
            log_activity('RETURN', f"Processed return for sale #{sale_id}", 'sale_returns', sale_id)
            
            return True
            
        except Exception as e:
            conn.rollback()
            raise e
    
    @staticmethod
    def get_sales_by_shift(shift_id):
        """Get all sales for a specific shift."""
        return Sale.get_all(shift_id)
