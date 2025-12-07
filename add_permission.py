"""Add activity_logs permission to ahmed user."""
import pyodbc

# Read connection string from config
with open(r'C:\Program Files\Elmohandes\config.txt', 'r') as f:
    connection_string = f.read().strip()

# Connect to database
conn = pyodbc.connect(connection_string, autocommit=True)
cursor = conn.cursor()

# Get current permissions
cursor.execute("SELECT username, permissions FROM users WHERE username = 'ahmed'")
result = cursor.fetchone()

if result:
    print(f"Current user: {result[0]}")
    print(f"Current permissions: {result[1]}")
    
    # Add activity_logs if not exists
    if 'activity_logs' not in result[1]:
        new_permissions = result[1] + ',activity_logs'
        cursor.execute("UPDATE users SET permissions = ? WHERE username = 'ahmed'", [new_permissions])
        print(f"\n✓ Updated permissions: {new_permissions}")
    else:
        print("\n✓ User already has activity_logs permission")
else:
    print("User 'ahmed' not found")

conn.close()
