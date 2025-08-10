import asyncio
import httpx
from database_manager import db_manager
import json
from datetime import datetime, timedelta

class TokenCache:
    def __init__(self):
        # دیگر نیاز به db_path نداریم چون db_manager خودش مدیریت می‌کنه
        self.setup_database()

    def setup_database(self):
        """
        Create database tables if they don't exist, with syntax
        compatible for both SQLite and PostgreSQL.
        """
        # هوشمندانه نوع کلید اصلی را بر اساس نوع دیتابیس انتخاب می‌کند
        primary_key_type = "SERIAL PRIMARY KEY" if db_manager.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"

        # 1. جدول توکن‌های ترند
        db_manager.execute('''
            CREATE TABLE IF NOT EXISTS trending_tokens (
                address TEXT PRIMARY KEY,
                symbol TEXT,
                pool_id TEXT,
                volume_24h REAL,
                price_usd REAL,
                updated_at TEXT
            )
        ''')

        # 2. جدول ساختار بازار (سطوح حمایت/مقاومت)
        db_manager.execute(f'''
            CREATE TABLE IF NOT EXISTS alert_history (
                id {primary_key_type},
                token_address TEXT,
                alert_type TEXT,
                timestamp TEXT,
                price_at_alert REAL,
                level_price REAL
            )
        ''')

        # 3. جدول وضعیت اندیکاتورها
        db_manager.execute('''
            CREATE TABLE IF NOT EXISTS indicator_status (
                token_address TEXT PRIMARY KEY,
                price_vs_ema200 TEXT,
                rsi_14 REAL,
                macd_signal TEXT,
                volume_avg_20 REAL,
                last_updated TEXT
            )
        ''')

        # 5. جدول لیست پیگیری (Watchlist)
        db_manager.execute('''
            CREATE TABLE IF NOT EXISTS watchlist_tokens (
                address TEXT PRIMARY KEY,
                symbol TEXT,
                pool_id TEXT,
                first_seen TEXT,
                last_active TEXT,
                status TEXT DEFAULT 'active',
                last_message_id INTEGER DEFAULT NULL
            )
        ''')
        print("✅ Database tables checked/created successfully.")

    async def fetch_trending_tokens(self):
        """Fetch trending tokens from GeckoTerminal API"""
        url = "https://api.geckoterminal.com/api/v2/networks/solana/trending_pools"
        params = {
            'include': 'base_token,quote_token',
            'limit': '50'
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    return self.process_trending_data(data)
        except Exception as e:
            print(f"Error fetching trending tokens: {e}")
        return []

    def process_trending_data(self, data):
        """Process and save trending data to database"""
        tokens = []
        pools = data.get('data', [])
        included = data.get('included', [])
        
        # Create a map of included tokens
        token_map = {}
        for item in included:
            if item.get('type') == 'token':
                token_id = item.get('id')
                token_attrs = item.get('attributes', {})
                token_map[token_id] = {
                    'address': token_attrs.get('address', ''),
                    'symbol': token_attrs.get('symbol', 'Unknown')
                }
        
        for pool in pools:
            try:
                attributes = pool.get('attributes', {})
                relationships = pool.get('relationships', {})
                
                # Get base token info from relationships
                base_token_rel = relationships.get('base_token', {}).get('data', {})
                base_token_id = base_token_rel.get('id', '')
                base_token_info = token_map.get(base_token_id, {})
                
                token_address = base_token_info.get('address', '')
                token_symbol = base_token_info.get('symbol', 'Unknown')
                base_token_price = attributes.get('base_token_price_usd')
                
                if not token_address or not base_token_price:
                    continue
                    
                token_data = {
                    'address': token_address,
                    'symbol': token_symbol,
                    'pool_id': pool.get('id', ''),
                    'volume_24h': float(attributes.get('volume_usd', {}).get('h24', 0)),
                    'price_usd': float(base_token_price)
                }
                tokens.append(token_data)
            except (ValueError, TypeError, KeyError) as e:
                continue
        
        # فقط یک بار ذخیره کن!
        if tokens:
            self.save_tokens(tokens)
        
        return tokens

    def save_tokens(self, tokens):
        """Save a list of tokens to the database in a single transaction (Upsert)."""
        if not tokens:
            return

        current_time = datetime.now().isoformat()
        data_to_save = [
            (
                token['address'],
                token['symbol'],
                token['pool_id'],
                token['volume_24h'],
                token['price_usd'],
                current_time
            ) for token in tokens
        ]

        if db_manager.is_postgres:
            # سینتکس PostgreSQL برای عملیات "upsert" (update or insert)
            # از %s به عنوان placeholder استفاده می‌کند
            query = """
                INSERT INTO trending_tokens (address, symbol, pool_id, volume_24h, price_usd, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (address) DO UPDATE SET
                    symbol = EXCLUDED.symbol,
                    pool_id = EXCLUDED.pool_id,
                    volume_24h = EXCLUDED.volume_24h,
                    price_usd = EXCLUDED.price_usd,
                    updated_at = EXCLUDED.updated_at;
            """
        else:
            # سینتکس SQLite برای همین عملیات
            # از ? به عنوان placeholder استفاده می‌کند
            query = """
                INSERT OR REPLACE INTO trending_tokens (address, symbol, pool_id, volume_24h, price_usd, updated_at)
                VALUES (?, ?, ?, ?, ?, ?);
            """

        # ما نیاز به یک متد executemany در db_manager داریم.
        # فرض می‌کنیم آن را اضافه کرده‌ایم یا خواهیم کرد.
        # فعلا برای سادگی، در یک تراکنش اجرا می‌کنیم.
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, data_to_save)
                conn.commit()
            print(f"Saved/Updated {len(tokens)} trending tokens to database")
            self.add_to_watchlist(tokens)
        except Exception as e:
            print(f"Error in save_tokens: {e}")
 
    def add_to_watchlist(self, tokens):
        """Add tokens to watchlist if not already exists"""
        if not tokens:
            return

        current_time = datetime.now().isoformat()
        data_to_save = [
            (token['address'], token['symbol'], token['pool_id'], 
             current_time, current_time) for token in tokens
        ]

        if db_manager.is_postgres:
            query = """
                INSERT INTO watchlist_tokens (address, symbol, pool_id, first_seen, last_active, status)
                VALUES (%s, %s, %s, %s, %s, 'active')
                ON CONFLICT (address) DO NOTHING
            """
        else:
            query = """
                INSERT OR IGNORE INTO watchlist_tokens 
                (address, symbol, pool_id, first_seen, last_active, status)
                VALUES (?, ?, ?, ?, ?, 'active')
            """

        try:
            db_manager.executemany(query, data_to_save)
            print(f"Added {len(tokens)} tokens to watchlist")
        except Exception as e:
            print(f"Error in add_to_watchlist: {e}")

    def get_watchlist_tokens(self, limit=150):
        """Get tokens from watchlist, prioritizing recently active ones"""
        placeholder = '%s' if db_manager.is_postgres else '?'
    
        query = f'''
            SELECT address, symbol, pool_id, first_seen, last_active, status
            FROM watchlist_tokens 
            WHERE status = 'active'
            ORDER BY last_active DESC 
            LIMIT {placeholder}
        '''
    
        results = db_manager.fetchall(query, (limit,))
    
        tokens = []
        for row in results:
            tokens.append({
                'address': row['address'],
                'symbol': row['symbol'],
                'pool_id': row['pool_id'],
                'first_seen': row['first_seen'],
                'last_active': row['last_active'],
                'status': row['status']
            })
    
        return tokens

    def get_trending_tokens(self, limit=10):
        """Get trending tokens from database"""
        placeholder = '%s' if db_manager.is_postgres else '?'
    
        query = f'''
            SELECT address, symbol, pool_id, volume_24h, price_usd, updated_at
            FROM trending_tokens 
            ORDER BY volume_24h DESC 
            LIMIT {placeholder}
        '''
    
        results = db_manager.fetchall(query, (limit,))
    
        tokens = []
        for row in results:
            tokens.append({
                'address': row['address'],
                'symbol': row['symbol'],
                'pool_id': row['pool_id'],
                'volume_24h': row['volume_24h'],
                'price_usd': row['price_usd'],
                'updated_at': row['updated_at']
            })
    
        return tokens

