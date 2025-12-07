"""User model."""
from database.db import get_db


class User:
    """Model for managing system users."""
    
    @staticmethod
    def get_all():
        """Get all users."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, permissions FROM users")
        return cursor.fetchall()
    
    @staticmethod
    def get_by_id(user_id):
        """Get user by ID."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, permissions FROM users WHERE id = ?", [user_id])
        return cursor.fetchone()
    
    @staticmethod
    def get_by_username(username):
        """Get user by username."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", [username])
        return cursor.fetchone()
    
    @staticmethod
    def authenticate(username, password):
        """Authenticate user with username and password."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, permissions 
            FROM users 
            WHERE username = ? AND password = ?
        """, [username, password])
        return cursor.fetchone()
    
    @staticmethod
    def create(data):
        """Create a new user."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, password, permissions)
            VALUES (?, ?, ?);
            SELECT SCOPE_IDENTITY() AS id
        """, [data['username'], data['password'], data.get('permissions', '')])
        result = cursor.fetchone()
        conn.commit()
        return int(result[0]) if result else None
    
    @staticmethod
    def update(user_id, data):
        """Update an existing user."""
        conn = get_db()
        cursor = conn.cursor()
        
        if 'password' in data and data['password']:
            cursor.execute("""
                UPDATE users SET username = ?, password = ?, permissions = ?
                WHERE id = ?
            """, [data['username'], data['password'], data.get('permissions', ''), user_id])
        else:
            cursor.execute("""
                UPDATE users SET username = ?, permissions = ?
                WHERE id = ?
            """, [data['username'], data.get('permissions', ''), user_id])
        
        conn.commit()
        return cursor.rowcount
    
    @staticmethod
    def delete(user_id):
        """Delete a user."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", [user_id])
        conn.commit()
        return cursor.rowcount
