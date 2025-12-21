"""Database connection with Singleton Pattern."""
import pyodbc
import os
import threading
from flask import g


class DatabaseConnection:
    """Singleton class for managing database connections."""
    
    _instance = None
    _lock = threading.Lock()
    _connection_string = None
    
    def __new__(cls):
        """Ensure only one instance exists (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def set_connection_string(cls, connection_string):
        """Set the connection string for the database."""
        cls._connection_string = connection_string
    
    def get_connection(self):
        """Get database connection with singleton pattern."""
        if not hasattr(g, 'db'):
            try:
                if not self._connection_string:
                    # Read from config file if not set
                    config_path = r'C:\Program Files\Elmohandes\config.txt'
                    if not os.path.exists(config_path):
                        raise Exception(f"Config file not found: {config_path}")
                    with open(config_path, 'r') as f:
                        connection_string = f.read().strip()
                else:
                    connection_string = self._connection_string
                
                g.db = pyodbc.connect(connection_string)
                g.db.autocommit = True
                print("Database connected successfully (Singleton)")
            except pyodbc.Error as e:
                print(f"Database connection error: {e}")
                raise Exception(f"Database connection error: {str(e)}")
            except Exception as e:
                print(f"Error reading configuration: {e}")
                raise Exception(f"Configuration error: {str(e)}")
        return g.db
    
    def close_connection(self):
        """Close database connection."""
        db = g.pop('db', None)
        if db is not None:
            try:
                if not db.closed:
                    db.close()
                    print("Database connection closed successfully")
            except Exception as e:
                print(f"Error closing database: {e}")


# Global singleton instance
_db_singleton = DatabaseConnection()


def get_db():
    """Get database connection from singleton."""
    return _db_singleton.get_connection()


def close_db(e=None):
    """Close database connection."""
    _db_singleton.close_connection()


def set_connection_string(connection_string):
    """Set custom connection string."""
    DatabaseConnection.set_connection_string(connection_string)


def init_app(app):
    """Initialize the Flask application."""
    app.teardown_appcontext(close_db)

def begin_transaction(db):
    """Begin a new transaction"""
    if db and not db.autocommit:
        cursor = db.cursor()
        cursor.execute("BEGIN TRANSACTION")
        return cursor
    return None

def commit_transaction(db):
    """Commit the current transaction"""
    if db and not db.autocommit:
        try:
            db.commit()
            print("Transaction committed successfully")
        except Exception as e:
            db.rollback()
            print(f"Transaction rollback due to: {e}")
            raise

def rollback_transaction(db):
    """Rollback the current transaction"""
    if db and not db.autocommit:
        try:
            db.rollback()
            print("Transaction rolled back")
        except Exception as e:
            print(f"Rollback failed: {e}")