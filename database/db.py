import pyodbc
import os
from flask import g, current_app

def get_db():
    """Get database connection"""
    if not hasattr(g, 'db'):
        try:
            # Read connection string from config file
            config_path = r'C:\Program Files\Elmohandes\config.txt'
            
            if not os.path.exists(config_path):
                raise Exception(f"ملف الإعدادات غير موجود في: {config_path}")
            
            with open(config_path, 'r') as f:
                connection_string = f.read().strip()
            
            g.db = pyodbc.connect(connection_string)
            g.db.autocommit = True
            print("Database connected successfully")
        except pyodbc.Error as e:
            print(f"Database connection error: {e}")
            raise Exception(f"خطأ في الاتصال بقاعدة البيانات: {str(e)}")
        except Exception as e:
            print(f"Error reading configuration: {e}")
            raise Exception(f"خطأ في الاتصال بالخادم: {str(e)}")
    return g.db

def close_db(e=None):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        try:
            if not db.closed:
                db.close()
                print("Database connection closed successfully")
        except Exception as e:
            print(f"Error closing database: {e}")

def init_app(app):
    """Initialize the Flask application"""
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