import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sqlite3
from analysis_engine import AnalysisEngine

class StrategyEngine:
   def __init__(self, db_path="tokens.db"):
       self.db_path = db_path
       self.analysis_engine = AnalysisEngine(db_path)

   async def detect_breakout_signal(self, token_address, pool_id, symbol):
       """
       Detects breakout signals for a token using a simplified rolling-high resistance.
       NOTE: This is a temporary, simplified version for initial testing.
       """
       # Get historical data
       df = await self.analysis_engine.get_historical_data(pool_id, "minute", "15", 100)

       if df is None or df.empty or len(df) < 50:
           return None

       # --- Simplified Resistance Detection ---
       # We will replace this with our advanced `find_major_zones` later.
       resistance_level = df['high'].rolling(window=20).max().iloc[-5] # Resistance from 5 candles ago

       # Get current market data from the last candle
       last_candle = df.iloc[-1]
       current_price = last_candle['close']
       current_volume = last_candle['volume']
       avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]

       # --- Breakout Conditions ---
       if pd.isna(resistance_level) or pd.isna(avg_volume):
            return None # Not enough data for calculation

       volume_spike = current_volume > (avg_volume * 1.5)  # 1.5x volume
       price_breakout = current_price > resistance_level    # واقعی breakout

       print(f"   Debug: Price {current_price:.6f} vs Resistance {resistance_level:.6f}, Volume {current_volume/avg_volume:.1f}x")

       if price_breakout and volume_spike:
           print(f"✅ BREAKOUT SIGNAL DETECTED for {symbol}!")
           return {
               'token_address': token_address,
               'symbol': symbol,
               'signal_type': 'breakout',
               'current_price': current_price,
               'resistance_level': resistance_level,
               'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 0,
               'timestamp': datetime.now().isoformat()
           }

       return None

   async def save_alert(self, signal):
       """Save alert to database"""
       conn = sqlite3.connect(self.db_path)
       cursor = conn.cursor()

       cursor.execute('''
           INSERT INTO alert_history
           (token_address, alert_type, timestamp, price_at_alert)
           VALUES (?, ?, ?, ?)
       ''', (signal['token_address'], signal['signal_type'],
             signal['timestamp'], signal['current_price']))

       conn.commit()
       conn.close()
       print(f"💾 Alert saved to database for {signal['symbol']}")
