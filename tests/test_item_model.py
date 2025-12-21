"""Unit tests for Item model using Repository Pattern."""
import unittest
from unittest.mock import Mock, patch, MagicMock
from models.item import Item


class TestItemModel(unittest.TestCase):
    """Test cases for Item model with repository pattern."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.item = Item()
    
    @patch('repositories.item_repository.ItemRepository.get_by_id')
    def test_get_by_id(self, mock_repo_method):
        """Test Item.get_by_id delegates to repository."""
        # Mock database response
        mock_item = (1, 'ABC123', 'Test Item', 1, 10.00, 15.00, 5, 1, 1, None, 'Electronics', 'Supplier A')
        mock_repo_method.return_value = mock_item
        
        # Call method
        result = self.item.get_by_id(1)
        
        # Assertions
        self.assertEqual(result, mock_item)
        mock_repo_method.assert_called_once_with(1)
    
    @patch('repositories.item_repository.ItemRepository.get_by_barcode')
    def test_get_by_barcode(self, mock_repo_method):
        """Test Item.get_by_barcode delegates to repository."""
        # Mock database response
        mock_item = (1, 'ABC123', 'Test Item', 1, 10.00, 15.00, 5, 1, 1, None, 'Electronics', 'Supplier A')
        mock_repo_method.return_value = mock_item
        
        # Call method
        result = self.item.get_by_barcode('ABC123')
        
        # Assertions
        self.assertEqual(result, mock_item)
        mock_repo_method.assert_called_once_with('ABC123')
    
    @patch('repositories.item_repository.ItemRepository.get_all')
    def test_get_all_active_items(self, mock_repo_method):
        """Test Item.get_all delegates to repository."""
        # Mock database response
        mock_items = [
            (1, 'ABC123', 'Item 1', 1, 10.00, 15.00, 5, 1, 1, None, 'Electronics', 'Supplier A'),
            (2, 'DEF456', 'Item 2', 2, 20.00, 25.00, 10, 2, 1, None, 'Books', 'Supplier B')
        ]
        mock_repo_method.return_value = mock_items
        
        # Call method
        result = self.item.get_all(include_deleted=False)
        
        # Assertions
        self.assertEqual(len(result), 2)
        self.assertEqual(result, mock_items)
        mock_repo_method.assert_called_once_with(False)


if __name__ == '__main__':
    unittest.main()
