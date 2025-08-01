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
db_manager = DatabaseManager()
