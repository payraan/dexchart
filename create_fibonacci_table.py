from database_manager import db_manager

# Create fibonacci_state table
try:
    db_manager.execute('''
        CREATE TABLE IF NOT EXISTS fibonacci_state (
            id SERIAL PRIMARY KEY,
            token_address TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            high_point DOUBLE PRECISION NOT NULL,
            low_point DOUBLE PRECISION NOT NULL,
            target1_price DOUBLE PRECISION,
            target2_price DOUBLE PRECISION,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(token_address, timeframe)
        );
    ''')
    print("✅ fibonacci_state table created successfully")
except Exception as e:
    print(f"❌ Error creating table: {e}")
