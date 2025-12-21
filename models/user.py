"""User model."""
from repositories.user_repository import UserRepository


class User:
    """Model for managing system users."""
    
    def __init__(self):
        """Initialize with repository."""
        self.repository = UserRepository()
    
    def get_all(self):
        """Get all users."""
        return self.repository.get_all()
    
    def get_by_id(self, user_id):
        """Get user by ID."""
        return self.repository.get_by_id(user_id)
    
    def get_by_username(self, username):
        """Get user by username."""
        return self.repository.get_by_username(username)
    
    def authenticate(self, username, password):
        """Authenticate user with username and password."""
        return self.repository.authenticate(username, password)
    
    def create(self, data):
        """Create a new user."""
        return self.repository.create(data)
    
    def update(self, user_id, data):
        """Update an existing user."""
        return self.repository.update(user_id, data)
    
    def delete(self, user_id):
        """Delete a user."""
        return self.repository.delete(user_id)
    
    def update_permissions(self, user_id, permissions):
        """Update user permissions."""
        return self.repository.update_permissions(user_id, permissions)
