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
       Detects breakout signals using advanced major zones analysis
       """
       # Configuration
       ZONE_SCORE_MIN = 3.0  # Minimum score for significant zones
    
       # Get historical data (1H for zones, 15M for detection)
       df_1h = await self.analysis_engine.get_historical_data(pool_id, "hour", "1", 200)
       df_15m = await self.analysis_engine.get_historical_data(pool_id, "minute", "15", 100)

       if df_1h is None or df_1h.empty or len(df_1h) < 50:
           return None
       if df_15m is None or df_15m.empty or len(df_15m) < 20:
           return None

       # --- Advanced Zone Detection (1H timeframe) ---
       supply_zones, demand_zones = self.analysis_engine.find_major_zones(df_1h, period=5)
    
       # Filter only high-score zones
       significant_supply = [zone for zone in supply_zones if zone['score'] >= ZONE_SCORE_MIN]
       significant_demand = [zone for zone in demand_zones if zone['score'] >= ZONE_SCORE_MIN]
    
       if not significant_supply and not significant_demand:
           return None

       # --- Current Market Data (15M timeframe) ---
       last_candle = df_15m.iloc[-1]
       current_price = last_candle['close']
       current_volume = last_candle['volume']
       avg_volume = df_15m['volume'].rolling(window=20).mean().iloc[-1]

       # --- Breakout Detection ---
       if pd.isna(avg_volume) or avg_volume <= 0:
           return None

       #volume_spike = current_volume > (avg_volume * 0.5)  # 1.5x volume requirement
       volume_spike = True  # برای تست major zones    

       # Check supply zone breakouts (bullish)
       for zone in significant_supply:
           if current_price > zone['avg_price'] and volume_spike:
               print(f"✅ MAJOR SUPPLY BREAKOUT for {symbol}! Score: {zone['score']:.1f}")
               return {
                   'token_address': token_address,
                   'pool_id': pool_id,
                   'symbol': symbol,
                   'signal_type': 'supply_breakout',
                   'current_price': current_price,
                   'resistance_level': zone['avg_price'],
                   'zone_score': zone['score'],
                   'volume_ratio': current_volume / avg_volume,
                   'timestamp': datetime.now().isoformat()
               }
    
       # Check demand zone breakdowns (bearish - optional for shorts)
       for zone in significant_demand:
           if current_price < zone['avg_price'] and volume_spike:
               print(f"✅ MAJOR DEMAND BREAKDOWN for {symbol}! Score: {zone['score']:.1f}")
               return {
                   'token_address': token_address,
                   'pool_id': pool_id,
                   'symbol': symbol,
                   'signal_type': 'demand_breakdown',
                   'current_price': current_price,
                   'support_level': zone['avg_price'],
                   'zone_score': zone['score'],
                   'volume_ratio': current_volume / avg_volume,
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
