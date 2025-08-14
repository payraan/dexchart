from database_manager import db_manager

# ایجاد جدول zone states
db_manager.execute('''
    CREATE TABLE IF NOT EXISTS zone_states (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_address TEXT,
        zone_price REAL,
        zone_tier TEXT,
        current_state TEXT,
        last_signal_type TEXT,
        last_signal_time TEXT,
        last_price REAL,
        UNIQUE(token_address, zone_price)
    )
''')

print("✅ Zone states table created")
