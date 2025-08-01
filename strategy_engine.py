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
       سیگنال‌های شکست را با استفاده از تحلیل چند تایم‌فریمی و کیفیت کندل تشخیص می‌دهد.
       - تایم‌فریم 1H: برای شناسایی سطوح اصلی عرضه.
       - تایم‌فریم 4H و 1H: برای تایید روند کلی.
       - تایم‌فریم 15M: برای تشخیص نقطه دقیق شکست و کیفیت آن.
       """
       # --- ۱. کانفیگ و تنظیمات ---
       ZONE_SCORE_MIN = 3.5  # حداقل امتیاز برای یک سطح معتبر
       VOLUME_SPIKE_MULTIPLIER = 2.0  # حجم باید حداقل 2 برابر میانگین باشد
       CANDLE_BODY_RATIO_MIN = 0.6  # حداقل 60% کندل باید بدنه باشد

       # --- ۲. دریافت دیتا از تایم‌فریم‌های مختلف ---
       df_1h = await self.analysis_engine.get_historical_data(pool_id, "hour", "1", 200)
       df_4h = await self.analysis_engine.get_historical_data(pool_id, "hour", "4", 100)
       df_15m = await self.analysis_engine.get_historical_data(pool_id, "minute", "15", 100)

       # اطمینان از وجود دیتای کافی
       if df_1h is None or df_1h.empty or len(df_1h) < 50: return None
       if df_4h is None or df_4h.empty or len(df_4h) < 10: return None
       if df_15m is None or df_15m.empty or len(df_15m) < 20: return None

       # --- ۳. شناسایی سطوح اصلی مقاومت (با استفاده از تایم فریم ۱ ساعته) ---
       supply_zones, _ = self.analysis_engine.find_major_zones(df_1h, period=5)
       significant_supply = [zone for zone in supply_zones if zone['score'] >= ZONE_SCORE_MIN]
       if not significant_supply:
           return None

       print(f"🔍 DEBUG {symbol}: Found {len(significant_supply)} supply zones with score 3.5+")

       # --- ۴. تایید روند در تایم‌فریم‌های بالاتر ---
       last_candle_1h = df_1h.iloc[-1]
       last_candle_4h = df_4h.iloc[-1]
       is_1h_bullish = last_candle_1h['close'] > last_candle_1h['open']
       is_4h_bullish = last_candle_4h['close'] > last_candle_4h['open']

       # فقط زمانی روند را بررسی کن که هر دو تایم فریم اصلی قرمز هستند
       trend_is_strong_bearish = False
       if not is_1h_bullish and not is_4h_bullish:
           # بررسی ۳ کندل آخر ۴ ساعته برای سنجش قدرت روند نزولی
           last_3_candles_4h = df_4h.iloc[-3:]
           bearish_count = (last_3_candles_4h['close'] < last_3_candles_4h['open']).sum()
           print(f"🔍 DEBUG {symbol}: آخرین 3 کندل 4H - bearish count: {bearish_count}/3")        

           # اگر حداقل ۲ از ۳ کندل آخر نزولی باشد، روند به طور کلی قوی نزولی است
           if bearish_count >= 3:  # فقط اگه 3 از 3 کندل قرمز باشن
               trend_is_strong_bearish = True

       if trend_is_strong_bearish:
           print(f"❌ DEBUG {symbol}: روند قوی نزولی در تایم‌فریم بالاتر تشخیص داده شد. سیگنال رد شد.")
           return None
    
       print(f"✅ DEBUG {symbol}: روند در تایم‌فریم بالاتر تایید شد (1H Bullish: {is_1h_bullish}, 4H Bullish: {is_4h_bullish}).")

       # --- ۵. بررسی دقیق شکست در تایم فریم ۱۵ دقیقه ---
       last_candle_15m = df_15m.iloc[-1]
       avg_volume_15m = df_15m['volume'].rolling(window=20).mean().iloc[-1]

       if pd.isna(avg_volume_15m) or avg_volume_15m <= 0:
           return None

       # حلقه برای بررسی شکست هر سطح مقاومت
       for zone in significant_supply:
           zone_price = zone['avg_price']

           # شرط اصلی شکست: آیا آخرین کندل ۱۵ دقیقه بالای سطح بسته شده است؟
           if last_candle_15m['close'] > zone_price:
            
               # شرط تایید ۱: آیا حجم معاملات افزایش چشمگیری داشته؟
               # نکته: برای تست می‌توانید این خط را موقتاً True قرار دهید
               volume_spike = last_candle_15m['volume'] > (avg_volume_15m * VOLUME_SPIKE_MULTIPLIER)

               # شرط تایید ۲: آیا کندل شکست، یک کندل قدرتمند است؟
               candle_high = last_candle_15m['high']
               candle_low = last_candle_15m['low']
               candle_body = abs(last_candle_15m['close'] - last_candle_15m['open'])
               candle_range = candle_high - candle_low

               is_quality_candle = False
               if candle_range > 0:
                   body_ratio = candle_body / candle_range
                   if body_ratio >= CANDLE_BODY_RATIO_MIN:
                       is_quality_candle = True

               # --- ۶. تایید نهایی و ارسال سیگنال ---
               if volume_spike and is_quality_candle:
                   print(f"✅ BREAKOUT چند تایم‌فریمی برای {symbol}! امتیاز سطح: {zone['score']:.1f}")
                   return {
                       'token_address': token_address,
                       'pool_id': pool_id,
                       'symbol': symbol,
                       'signal_type': 'multi_tf_breakout',
                       'current_price': last_candle_15m['close'],
                       'resistance_level': zone_price,
                       'zone_score': zone['score'],
                       'volume_ratio': last_candle_15m['volume'] / avg_volume_15m,
                       'timestamp': datetime.now().isoformat()
                   }

       # اگر هیچ سیگنال معتبری یافت نشد
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
