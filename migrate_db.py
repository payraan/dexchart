from database_manager import db_manager

def migrate_database():
    try:
        # Add level_price column to existing table
        db_manager.execute("ALTER TABLE alert_history ADD COLUMN level_price REAL")
        print("✅ Migration successful: level_price column added")
    except Exception as e:
        print(f"Migration info: {e}")

if __name__ == "__main__":
    migrate_database()
