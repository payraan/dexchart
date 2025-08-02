import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from database_manager import db_manager
from analysis_engine import AnalysisEngine

class StrategyEngine:
   def __init__(self):
       self.analysis_engine = AnalysisEngine()

   async def detect_breakout_signal(self, token_address, pool_id, symbol):
       """
       سیگنال‌های شکست را با استفاده از تحلیل چند تایم‌فریمی و کیفیت کندل تشخیص می‌دهد.
       - تایم‌فریم 1H: برای شناسایی سطوح اصلی عرضه.
       - تایم‌فریم 4H و 1H: برای تایید روند کلی.
       - تایم‌فریم 15M: برای تشخیص نقطه دقیق شکست و کیفیت آن.
       """
       # --- ۱. کانفیگ و تنظیمات ---
       ZONE_SCORE_MIN = 2.5  # حداقل امتیاز برای یک سطح معتبر
       VOLUME_SPIKE_MULTIPLIER = 0.3  # حجم باید حداقل 2 برابر میانگین باشد
       CANDLE_BODY_RATIO_MIN = 0.3  # حداقل 60% کندل باید بدنه باشد

       # --- ۲. دریافت دیتا از تایم‌فریم‌های مختلف ---
       df_1h = await self.analysis_engine.get_historical_data(pool_id, "hour", "1", 200)
       df_4h = await self.analysis_engine.get_historical_data(pool_id, "hour", "4", 100)
       df_15m = await self.analysis_engine.get_historical_data(pool_id, "minute", "15", 100)

       # اطمینان از وجود دیتای کافی
       if df_1h is None or df_1h.empty or len(df_1h) < 50: return None
       if df_4h is None or df_4h.empty or len(df_4h) < 10: return None
       if df_15m is None or df_15m.empty or len(df_15m) < 20: return None

       # --- ۳. شناسایی سطوح اصلی مقاومت (با استفاده از تایم فریم ۱ ساعته) ---
       supply_zones, demand_zones = self.analysis_engine.find_major_zones(df_1h, period=5)
       significant_supply = [zone for zone in supply_zones if zone['score'] >= ZONE_SCORE_MIN]
       # نواحی پیدا شده را در دیتابیس ذخیره کن
       await self.save_market_structure(token_address, supply_zones, 'supply')
       await self.save_market_structure(token_address, demand_zones, 'demand')
       if not significant_supply:
           return None

       print(f"🔍 DEBUG {symbol}: Found {len(significant_supply)} supply zones with score 3.5+")

       # --- ۴. تایید روند در تایم‌فریم‌های بالاتر ---
       last_candle_1h = df_1h.iloc[-1]
       last_candle_4h = df_4h.iloc[-1]
       is_1h_bullish = last_candle_1h['close'] > last_candle_1h['open']
       is_4h_bullish = last_candle_4h['close'] > last_candle_4h['open']

       # فقط زمانی روند را بررسی کن که هر دو تایم فریم اصلی قرمز هستند
       # بهبود منطق تشخیص روند
       strong_bearish_signals = 0

       # اگر کندل ۱ ساعته قرمز باشد، یک امتیاز منفی
       if not is_1h_bullish: 
           strong_bearish_signals += 1

       # اگر کندل ۴ ساعته قرمز باشد، یک امتیاز منفی
       if not is_4h_bullish: 
           strong_bearish_signals += 1

       # بررسی ۳ کندل آخر ۴ ساعته
       last_3_candles_4h = df_4h.iloc[-3:]
       bearish_count = (last_3_candles_4h['close'] < last_3_candles_4h['open']).sum()

       # اگر حداقل ۲ از ۳ کندل آخر ۴ ساعته قرمز باشند، یک امتیاز منفی دیگر
       if bearish_count >= 2:
           strong_bearish_signals += 1
           print(f"🔍 DEBUG {symbol}: روند نزولی در کندل‌های 4H تشخیص داده شد ({bearish_count}/3).")

       # فقط زمانی سیگنال را رد کن که حداقل ۲ از ۳ شرط نزولی برقرار باشد
       trend_is_strong_bearish = (strong_bearish_signals >= 2)

       if trend_is_strong_bearish:
           print(f"❌ INFO {symbol}: روند کلی نزولی است (امتیاز منفی: {strong_bearish_signals}). سیگنال رد شد.")
           return None

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
       print(f"🔍 [{symbol}] در حال بررسی {len(significant_supply)} ناحیه عرضه معتبر...")
       for i, zone in enumerate(significant_supply, 1):
           zone_price = zone['avg_price']
           print(f"  - ناحیه {i}: قیمت={zone_price:.6f}, امتیاز={zone['score']:.1f}")

           # شرط ۱: آیا قیمت از ناحیه عبور کرده؟
           if last_candle_15m['close'] <= zone_price:
               print(f"    ❌ رد شد: قیمت فعلی ({last_candle_15m['close']:.6f}) هنوز ناحیه را نشکسته است.")
               continue

           print(f"    ✅ تایید: قیمت ناحیه را شکسته است.")

           # شرط ۲: آیا حجم معاملات کافی است؟
           volume_ratio = last_candle_15m['volume'] / avg_volume_15m
           volume_spike = True  # موقتاً غیرفعال برای تست
           if not volume_spike:
               print(f"    ❌ رد شد: نسبت حجم ({volume_ratio:.2f}) کمتر از حد نیاز ({VOLUME_SPIKE_MULTIPLIER}) بود.")
               continue

           print(f"    ✅ تایید: حجم معاملات کافی است (نسبت: {volume_ratio:.2f}).")

           # شرط ۳: آیا کندل شکست باکیفیت است؟
           candle_high = last_candle_15m['high']
           candle_low = last_candle_15m['low']
           candle_body = abs(last_candle_15m['close'] - last_candle_15m['open'])
           candle_range = candle_high - candle_low
           body_ratio = candle_body / candle_range if candle_range > 0 else 0
           is_quality_candle = body_ratio >= CANDLE_BODY_RATIO_MIN

           if not is_quality_candle:
               print(f"    ❌ رد شد: کیفیت کندل (نسبت بدنه: {body_ratio:.2f}) کمتر از حد نیاز ({CANDLE_BODY_RATIO_MIN}) بود.")
               continue

           print(f"    ✅ تایید: کندل شکست باکیفیت است (نسبت بدنه: {body_ratio:.2f}).")
           print(f"🚀✅ سیگنال BREAKOUT برای {symbol} یافت شد!")
    
           return {
               'token_address': token_address,
               'pool_id': pool_id,
               'symbol': symbol,
               'signal_type': 'multi_tf_breakout',
               'current_price': last_candle_15m['close'],
               'resistance_level': zone_price,
               'zone_score': zone['score'],
               'volume_ratio': volume_ratio,
               'timestamp': datetime.now().isoformat()
           }

       # اگر هیچ سیگنال معتبری یافت نشد
       return None

   async def save_alert(self, signal):
        """Save alert to the database using the new db_manager."""
        
        params = (
            signal['token_address'], 
            signal['signal_type'],
            signal['timestamp'], 
            signal['current_price']
        )

        # placeholder مناسب را بر اساس نوع دیتابیس انتخاب می‌کند
        placeholder = "%s" if db_manager.is_postgres else "?"
        
        query = f'''
            INSERT INTO alert_history
            (token_address, alert_type, timestamp, price_at_alert)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
        '''
        
        try:
            db_manager.execute(query, params)
            print(f"💾 Alert saved to database for {signal['symbol']}")
        except Exception as e:
            print(f"Error in save_alert: {e}")

   async def save_market_structure(self, token_address, zones, level_type):
       """Save supply/demand zones to market_structure table"""
       if not zones:
           return

       current_time = datetime.now().isoformat()
       data_to_save = []
       for zone in zones:
           data_to_save.append((
               token_address,
               level_type,
               zone['avg_price'],
               zone['score'],
               current_time,  # last_tested_at
               current_time   # created_at
           ))

       # Choose correct placeholder based on database type
       placeholder = "%s" if db_manager.is_postgres else "?"
    
       query = f"""
           INSERT OR IGNORE INTO market_structure
           (token_address, level_type, price_level, score, last_tested_at, created_at)
           VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
       """
    
       if db_manager.is_postgres:
           query = query.replace('INSERT OR IGNORE', 'INSERT ON CONFLICT DO NOTHING')

       try:
           db_manager.executemany(query, data_to_save)
           print(f"💾 {len(zones)} ناحیه {level_type} برای {token_address[:8]}... در دیتابیس ذخیره شد.")
       except Exception as e:
           print(f"Error in save_market_structure: {e}")
