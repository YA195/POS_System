"""Unit tests for Repository and Singleton Pattern Implementation."""
import unittest
from unittest.mock import MagicMock, patch
from repositories.item_repository import ItemRepository
from repositories.category_repository import CategoryRepository
from repositories.user_repository import UserRepository
from models.item import Item
from models.category import Category
from models.user import User
from database.db import DatabaseConnection


class TestSingletonPattern(unittest.TestCase):
    """Test cases for Singleton Pattern."""
    
    def test_singleton_instance_creation(self):
        """Test that only one instance of DatabaseConnection is created."""
        db1 = DatabaseConnection()
        db2 = DatabaseConnection()
        
        # Both should be the same instance
        self.assertIs(db1, db2, "Singleton should return same instance")
    
    def test_singleton_multiple_calls(self):
        """Test singleton with multiple calls."""
        instances = [DatabaseConnection() for _ in range(5)]
        
        # All should be identical
        for instance in instances[1:]:
            self.assertIs(instances[0], instance)


class TestRepositoryPattern(unittest.TestCase):
    """Test cases for Repository Pattern."""
    
    def test_item_model_uses_repository(self):
        """Test that Item model uses ItemRepository."""
        item = Item()
        self.assertIsInstance(item.repository, ItemRepository)
    
    def test_category_model_uses_repository(self):
        """Test that Category model uses CategoryRepository."""
        category = Category()
        self.assertIsInstance(category.repository, CategoryRepository)
    
    def test_user_model_uses_repository(self):
        """Test that User model uses UserRepository."""
        user = User()
        self.assertIsInstance(user.repository, UserRepository)


class TestItemRepository(unittest.TestCase):
    """Test cases for ItemRepository."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.repository = ItemRepository()
    
    @patch('repositories.base_repository.get_db')
    def test_get_by_id(self, mock_get_db):
        """Test ItemRepository.get_by_id()."""
        mock_cursor = MagicMock()
        mock_item = (1, 'ABC123', 'Test Item', 1, 10.0, 15.0, 5, 1, 1, None, 'Electronics', 'Supplier')
        mock_cursor.fetchone.return_value = mock_item
        
        mock_db = MagicMock()
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db
        
        result = self.repository.get_by_id(1)
        
        self.assertEqual(result, mock_item)
        mock_cursor.execute.assert_called_once()
    
    @patch('repositories.base_repository.get_db')
    def test_get_all(self, mock_get_db):
        """Test ItemRepository.get_all()."""
        mock_cursor = MagicMock()
        mock_items = [
            (1, 'ABC123', 'Item 1', 1, 10.0, 15.0, 5, 1, 1, None, 'Electronics', 'Supplier'),
            (2, 'DEF456', 'Item 2', 2, 20.0, 25.0, 10, 2, 1, None, 'Books', 'Supplier 2')
        ]
        mock_cursor.fetchall.return_value = mock_items
        
        mock_db = MagicMock()
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db
        
        result = self.repository.get_all()
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result, mock_items)


class TestCategoryRepository(unittest.TestCase):
    """Test cases for CategoryRepository."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.repository = CategoryRepository()
    
    @patch('repositories.base_repository.get_db')
    def test_get_by_id(self, mock_get_db):
        """Test CategoryRepository.get_by_id()."""
        mock_cursor = MagicMock()
        mock_category = (1, 'Electronics', 0)
        mock_cursor.fetchone.return_value = mock_category
        
        mock_db = MagicMock()
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db
        
        result = self.repository.get_by_id(1)
        
        self.assertEqual(result, mock_category)
        mock_cursor.execute.assert_called_once()


class TestUserRepository(unittest.TestCase):
    """Test cases for UserRepository."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.repository = UserRepository()
    
    @patch('repositories.base_repository.get_db')
    def test_get_by_username(self, mock_get_db):
        """Test UserRepository.get_by_username()."""
        mock_cursor = MagicMock()
        mock_user = (1, 'admin', 'hashed_password', 'admin')
        mock_cursor.fetchone.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_db
        
        result = self.repository.get_by_username('admin')
        
        self.assertEqual(result, mock_user)
        mock_cursor.execute.assert_called_once()


class TestItemModel(unittest.TestCase):
    """Test cases for Item model using repository."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.item = Item()
    
    @patch.object(ItemRepository, 'get_by_id')
    def test_get_by_id_delegates_to_repository(self, mock_repo_method):
        """Test that Item.get_by_id delegates to repository."""
        mock_repo_method.return_value = (1, 'ABC123', 'Item', 1, 10.0, 15.0, 5, 1, 1, None)
        
        result = self.item.get_by_id(1)
        
        mock_repo_method.assert_called_once_with(1)
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
