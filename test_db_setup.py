from database_manager import db_manager

if db_manager.is_postgres:
    print("⚠️ Using PostgreSQL - Please run the SQL in Railway Dashboard")
else:
    # SQLite version برای تست لوکال
    db_manager.execute('''
        CREATE TABLE IF NOT EXISTS zone_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_address TEXT NOT NULL,
            zone_price REAL NOT NULL,
            zone_tier TEXT,
            current_state TEXT,
            last_signal_type TEXT,
            last_signal_time TEXT,
            last_price REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(token_address, zone_price)
        )
    ''')
    print("✅ SQLite zone_states table created locally")
