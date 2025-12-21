"""Unit tests for Item model."""
import unittest
from unittest.mock import Mock, patch, MagicMock
from models.item import Item


class TestItemModel(unittest.TestCase):
    """Test cases for Item model."""
    
    @patch('models.item.get_db')
    def test_get_by_id(self, mock_get_db):
        """Test retrieving item by ID."""
        # Mock database response
        mock_item = (1, 'ABC123', 'Test Item', 1, 10.00, 15.00, 5, 1, 1, None, 'Electronics', 'Supplier A')
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = mock_item
        mock_db = MagicMock()
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db
        
        # Call method
        result = Item.get_by_id(1)
        
        # Assertions
        self.assertEqual(result, mock_item)
        mock_cursor.execute.assert_called_once()
    
    @patch('models.item.get_db')
    def test_get_by_barcode(self, mock_get_db):
        """Test retrieving item by barcode."""
        # Mock database response
        mock_item = (1, 'ABC123', 'Test Item', 1, 10.00, 15.00, 5, 1, 1, None, 'Electronics', 'Supplier A')
        
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = mock_item
        mock_db = MagicMock()
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db
        
        # Call method
        result = Item.get_by_barcode('ABC123')
        
        # Assertions
        self.assertEqual(result, mock_item)
        mock_cursor.execute.assert_called_once()
    
    @patch('models.item.get_db')
    def test_get_all_active_items(self, mock_get_db):
        """Test retrieving all active items."""
        # Mock database response
        mock_items = [
            (1, 'ABC123', 'Item 1', 1, 10.00, 15.00, 5, 1, 1, None, 'Electronics', 'Supplier A'),
            (2, 'DEF456', 'Item 2', 2, 20.00, 25.00, 10, 2, 1, None, 'Books', 'Supplier B')
        ]
        
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_items
        mock_db = MagicMock()
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db
        
        # Call method
        result = Item.get_all(include_deleted=False)
        
        # Assertions
        self.assertEqual(len(result), 2)
        self.assertEqual(result, mock_items)
        mock_cursor.execute.assert_called_once()


if __name__ == '__main__':
    unittest.main()
