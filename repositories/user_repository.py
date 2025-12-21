"""User Repository - Data access layer for users."""
from repositories.base_repository import BaseRepository


class UserRepository(BaseRepository):
    """Repository for user database operations."""
    
    def __init__(self):
        """Initialize user repository."""
        super().__init__('users')
    
    def get_all(self):
        """Get all users."""
        query = "SELECT id, username, permissions FROM users"
        return self.execute_query(query)
    
    def get_by_id(self, user_id):
        """Get user by ID."""
        query = "SELECT id, username, permissions FROM users WHERE id = ?"
        return self.execute_query_one(query, [user_id])
    
    def get_by_username(self, username):
        """Get user by username."""
        query = "SELECT * FROM users WHERE username = ?"
        return self.execute_query_one(query, [username])
    
    def authenticate(self, username, password):
        """Authenticate user."""
        query = "SELECT id, username, permissions FROM users WHERE username = ? AND password = ?"
        return self.execute_query_one(query, [username, password])
    
    def create(self, data):
        """Create new user."""
        query = "INSERT INTO users (username, password, permissions) VALUES (?, ?, ?)"
        params = [data['username'], data['password'], data.get('permissions', '')]
        return self.create(query, params)
    
    def update(self, user_id, data):
        """Update user."""
        query = "UPDATE users SET username = ?, password = ?, permissions = ? WHERE id = ?"
        params = [data['username'], data['password'], data.get('permissions', ''), user_id]
        return self.update(query, params)
    
    def delete(self, user_id):
        """Delete user."""
        query = "DELETE FROM users WHERE id = ?"
        return self.delete(query, [user_id])
    
    def update_permissions(self, user_id, permissions):
        """Update user permissions."""
        query = "UPDATE users SET permissions = ? WHERE id = ?"
        return self.update(query, [permissions, user_id])
