import asyncio
import httpx
import sqlite3
import json
from datetime import datetime, timedelta

class TokenCache:
    def __init__(self, db_path="tokens.db"):
        self.db_path = db_path
        self.setup_database()

    def setup_database(self):
        """Create database tables if not exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
       
        # Original trending tokens table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trending_tokens (
                address TEXT PRIMARY KEY,
                symbol TEXT,
                pool_id TEXT,
                volume_24h REAL,
                price_usd REAL,
                updated_at TEXT
            )
        ''')
       
        # Market structure table for support/resistance levels
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_structure (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT,
                level_type TEXT,
                price_level REAL,
                score REAL,
                last_tested_at TEXT,
                created_at TEXT
            )
        ''')
       
        # Indicator status table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS indicator_status (
                token_address TEXT PRIMARY KEY,
                price_vs_ema200 TEXT,
                rsi_14 REAL,
                macd_signal TEXT,
                volume_avg_20 REAL,
                last_updated TEXT
            )
        ''')
       
        # Alert history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT,
                alert_type TEXT,
                timestamp TEXT,
                price_at_alert REAL
            )
        ''')
       
        conn.commit()
        conn.close()

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
        """Save a list of tokens to the database in a single transaction"""
        if not tokens:
            return

        # آماده‌سازی داده‌ها برای executemany
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

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # استفاده از executemany برای ذخیره‌سازی دسته‌ای
        cursor.executemany('''
            INSERT OR REPLACE INTO trending_tokens
            (address, symbol, pool_id, volume_24h, price_usd, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', data_to_save)

        conn.commit()
        conn.close()
        print(f"Saved/Updated {len(tokens)} trending tokens to database")
 
    def get_trending_tokens(self, limit=10):
        """Get trending tokens from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT address, symbol, pool_id, volume_24h, price_usd, updated_at
            FROM trending_tokens 
            ORDER BY volume_24h DESC 
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        tokens = []
        for row in results:
            tokens.append({
                'address': row[0],
                'symbol': row[1],
                'pool_id': row[2],
                'volume_24h': row[3],
                'price_usd': row[4],
                'updated_at': row[5]
            })
        
        return tokens 

    async def start_background_update(self, interval_minutes=10):
        """Start background task to update trending tokens every X minutes"""
        print(f"Starting background token updates every {interval_minutes} minutes...")
        
        while True:
            try:
                print("Fetching trending tokens...")
                tokens = await self.fetch_trending_tokens()
                if tokens:
                    print(f"Successfully updated {len(tokens)} trending tokens")
                else:
                    print("No tokens fetched this time")
            except Exception as e:
                print(f"Background update error: {e}")
            
            # Wait for next update
            await asyncio.sleep(interval_minutes * 60)

