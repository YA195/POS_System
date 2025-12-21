"""Unit tests for authentication decorators."""
import unittest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask
from utils.auth import login_required


class TestLoginRequired(unittest.TestCase):
    """Test cases for login_required decorator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_function = Mock(return_value="success")
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.request_context = self.app.test_request_context('/')
        self.request_context.push()
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.request_context.pop()
        self.app_context.pop()
    
    @patch('utils.auth.session', {})
    @patch('utils.auth.redirect')
    def test_login_required_no_session(self, mock_redirect):
        """Test that login_required redirects when no user_id in session."""
        # Create decorated function
        decorated = login_required(self.mock_function)
        
        # Call with empty session
        with patch('utils.auth.session', {}):
            with patch('utils.auth.redirect') as mock_redirect:
                with patch('utils.auth.url_for', return_value='/login'):
                    decorated()
                    mock_redirect.assert_called()
    
    def test_login_required_function_called(self):
        """Test that login_required calls wrapped function when user is in session."""
        # Mock session with user_id
        test_session = {'user_id': 1}
        
        # Mock database
        with patch('utils.auth.get_db') as mock_db:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1, 'testuser', 'admin')
            mock_db.return_value.cursor.return_value = mock_cursor
            
            # Create decorated function
            decorated = login_required(self.mock_function)
            
            # Call with session
            with patch('utils.auth.session', test_session):
                result = decorated()
                # Verify original function was called
                self.mock_function.assert_called_once()


if __name__ == '__main__':
    unittest.main()
