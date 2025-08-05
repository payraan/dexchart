import sqlite3
import psycopg2
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def add_column_if_not_exists(conn, cursor, table_name, column_name, column_type):
    try:
        cursor.execute(f"SELECT {column_name} FROM {table_name} LIMIT 0")
        logging.info(f"✅ ستون '{column_name}' از قبل وجود دارد.")
        return
    except (sqlite3.OperationalError, psycopg2.errors.UndefinedColumn):
        pass

    try:
        alter_query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        cursor.execute(alter_query)
        conn.commit()
        logging.info(f"✅ ستون '{column_name}' اضافه شد.")
    except Exception as e:
        logging.error(f"❌ خطا: {e}")
        conn.rollback()

def run_all_migrations():
    is_postgres = Config.DATABASE_URL.startswith(('postgresql://', 'postgres://'))
    
    try:
        if is_postgres:
            conn = psycopg2.connect(Config.DATABASE_URL)
        else:
            conn = sqlite3.connect(Config.DATABASE_URL)
            
        cursor = conn.cursor()
        logging.info("🚀 شروع migration...")

        # Migration 1: افزودن level_price
        add_column_if_not_exists(conn, cursor, "alert_history", "level_price", "REAL")
        
        # Migration 2: افزودن last_message_id  
        add_column_if_not_exists(conn, cursor, "watchlist_tokens", "last_message_id", "INTEGER DEFAULT NULL")
        
        # Migration 3: افزودن signal_type
        add_column_if_not_exists(conn, cursor, "alert_history", "signal_type", "TEXT")

        cursor.close()
        conn.close()
        logging.info("✅ تمام migration ها کامل شد.")

    except Exception as e:
        logging.critical(f"❌ خطای اتصال: {e}")

if __name__ == "__main__":
    run_all_migrations()
