import pyodbc
import os
from database.schema import TABLES

def init_database():
    try:
        # Read connection string from config file
        config_path = r'C:\Program Files\Elmohandes\config.txt'
        
        if not os.path.exists(config_path):
            raise Exception("Database configuration file not found")
        
        with open(config_path, 'r') as f:
            conn_str = f.read().strip()

        # Connect to SQL Server
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()

        # Create database if it doesn't exist
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'supermarket')
            BEGIN
                CREATE DATABASE supermarket;
            END
        """)
        
        # Close connection to master and connect to new database
        conn.close()
        conn_str += 'Database=supermarket;'
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Create tables in order (due to dependencies)
        for table_name, table_sql in TABLES.items():
            print(f"Creating table: {table_name}")
            cursor.execute(table_sql)
            conn.commit()

        print("Database initialization completed successfully")

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__": 
    init_database()