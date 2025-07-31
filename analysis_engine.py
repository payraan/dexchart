import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sqlite3
import httpx  # اضافه شده به imports
from token_cache import TokenCache

class AnalysisEngine:
    def __init__(self, db_path="tokens.db"):
        self.db_path = db_path
        self.token_cache = TokenCache(db_path)

    def calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    async def get_historical_data(self, pool_id, timeframe="hour", aggregate="1", limit=200):
        """Get historical OHLCV data for analysis"""
        network, pool_address = pool_id.split('_')
        url = f"https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}/ohlcv/{timeframe}"

        params = {
            'aggregate': aggregate,
            'limit': str(limit)
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    ohlcv_list = data.get('data', {}).get('attributes', {}).get('ohlcv_list', [])

                    # Convert to DataFrame
                    df_data = []
                    for candle in ohlcv_list:
                        timestamp, open_price, high, low, close, volume = candle
                        df_data.append({
                            'timestamp': timestamp,
                            'open': float(open_price),
                            'high': float(high),
                            'low': float(low),
                            'close': float(close),
                            'volume': float(volume)
                        })

                    df = pd.DataFrame(df_data)
                    if not df.empty:
                        df = df.sort_values('timestamp').reset_index(drop=True)
                    return df
        except Exception as e:
            print(f"Error fetching historical data: {e}")

        return pd.DataFrame()  # Return empty DataFrame instead of None

    async def analyze_token(self, token_address, pool_id):
        """Analyze a single token and update indicator status"""
        df = await self.get_historical_data(pool_id)
        
        if df.empty or len(df) < 50:
            return False
            
        # Calculate indicators
        df['rsi'] = self.calculate_rsi(df['close'])
        df['ema_200'] = df['close'].ewm(span=200).mean()
        df['volume_avg_20'] = df['volume'].rolling(20).mean()
        
        # Get latest values
        latest = df.iloc[-1]
        current_price = latest['close']
        current_rsi = latest['rsi']
        ema_200 = latest['ema_200']
        volume_avg = latest['volume_avg_20']
        
        # Determine price vs EMA200
        price_vs_ema200 = "above" if current_price > ema_200 else "below"
        
        # Save to database
        self.save_indicator_status(token_address, price_vs_ema200, current_rsi, "neutral", volume_avg)
        return True

    def save_indicator_status(self, token_address, price_vs_ema200, rsi_14, macd_signal, volume_avg_20):
        """Save indicator status to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_time = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT OR REPLACE INTO indicator_status
            (token_address, price_vs_ema200, rsi_14, macd_signal, volume_avg_20, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (token_address, price_vs_ema200, rsi_14, macd_signal, volume_avg_20, current_time))
        
        conn.commit()
        conn.close()
