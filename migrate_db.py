import os
import psycopg2
from config import Config

def migrate_database():
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(Config.DATABASE_URL)
        cursor = conn.cursor()
        
        # Add level_price column
        cursor.execute("ALTER TABLE alert_history ADD COLUMN level_price REAL")
        conn.commit()
        
        print("✅ Migration successful: level_price column added")
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Migration result: {e}")

if __name__ == "__main__":
    migrate_database()
