import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config
from contextlib import contextmanager

class DatabaseManager:
    def __init__(self):
        self.db_url = Config.DATABASE_URL
        # تشخیص خودکار نوع دیتابیس از روی URL
        self.is_postgres = self.db_url.startswith('postgresql://') or self.db_url.startswith('postgres://')

    @contextmanager
    def get_connection(self):
        """یک کانکشن به دیتابیس را در یک context manager فراهم می‌کند."""
        try:
            if self.is_postgres:
                conn = psycopg2.connect(self.db_url)
            else:
                conn = sqlite3.connect(self.db_url)
                # این خط باعث می‌شود خروجی SQLite هم شبیه دیکشنری باشد (برای هماهنگی با Postgres)
                conn.row_factory = sqlite3.Row
            yield conn
        finally:
            if 'conn' in locals() and conn:
                conn.close()

    def _execute_query(self, query, params=None, fetch=None):
        """یک متد داخلی برای اجرای انواع کوئری‌ها."""
        with self.get_connection() as conn:
            # برای Postgres از RealDictCursor استفاده می‌کنیم تا خروجی دیکشنری باشد
            if self.is_postgres:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cursor = conn.cursor()

            cursor.execute(query, params or [])

            if fetch == 'all':
                result = cursor.fetchall()
                # تبدیل خروجی sqlite3.Row به دیکشنری
                if not self.is_postgres and result:
                    result = [dict(row) for row in result]
            elif fetch == 'one':
                result = cursor.fetchone()
                if not self.is_postgres and result:
                    result = dict(result)
            else:
                conn.commit()
                result = cursor.rowcount  # تعداد سطرهای تغییر یافته را برمی‌گرداند

            cursor.close()
            return result

    # متدهای عمومی برای استفاده در بقیه کد
    def fetchall(self, query, params=None):
        return self._execute_query(query, params, fetch='all')

    def fetchone(self, query, params=None):
        return self._execute_query(query, params, fetch='one')

    def execute(self, query, params=None):
        """برای کوئری‌های INSERT, UPDATE, DELETE استفاده می‌شود."""
        return self._execute_query(query, params)

    def executemany(self, query, params_list):
        """Execute query with multiple parameter sets (batch operation)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount

# یک نمونه از کلاس می‌سازیم تا در همه جا از همین یک نمونه استفاده شود


    def get_fibo_state(self, token_address, timeframe):
        """Get fibonacci state for a token"""
        placeholder = "%s" if self.is_postgres else "?"
        query = f"SELECT * FROM fibonacci_state WHERE token_address = {placeholder} AND timeframe = {placeholder}"
        return self.fetchone(query, (token_address, timeframe))

    def upsert_fibo_state(self, state_data):
        """Insert or update fibonacci state"""
        if self.is_postgres:
            query = """
                INSERT INTO fibonacci_state (token_address, timeframe, high_point, low_point, target1_price, target2_price, status, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (token_address, timeframe) DO UPDATE SET
                    high_point = EXCLUDED.high_point,
                    low_point = EXCLUDED.low_point,
                    target1_price = EXCLUDED.target1_price,
                    target2_price = EXCLUDED.target2_price,
                    status = EXCLUDED.status,
                    updated_at = CURRENT_TIMESTAMP
            """
            params = (state_data['token_address'], state_data['timeframe'],
                      state_data['high_point'], state_data['low_point'],
                      state_data['target1_price'], state_data['target2_price'],
                      state_data['status'])
        else:
            query = """
                INSERT OR REPLACE INTO fibonacci_state (token_address, timeframe, high_point, low_point, target1_price, target2_price, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            params = (state_data['token_address'], state_data['timeframe'],
                     state_data['high_point'], state_data['low_point'],
                     state_data['target1_price'], state_data['target2_price'],
                     state_data['status'])
        # <<< این خط باید اینجا باشد
        return self.execute(query, params)

    def ensure_fibonacci_table(self):
        """Ensure fibonacci_state table exists"""
        try:
            self.execute('''
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
            print("✅ fibonacci_state table ensured")
        except Exception as e:
            print(f"❌ Error creating fibonacci_state table: {e}")

db_manager = DatabaseManager()
db_manager.ensure_fibonacci_table()
