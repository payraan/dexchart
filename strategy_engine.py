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
       سیگنال‌های شکست را با استفاده از یک استراتژی تطبیق‌پذیر تشخیص می‌دهد.
       - برای توکن‌های جدید: از تایم‌فریم‌های 15M (برای ساختار) و 5M (برای ورود) استفاده می‌کند.
       - برای توکن‌های بالغ: از تایم‌فریم‌های 1H (برای ساختار) و 15M (برای ورود) استفاده می‌کند.
       """
       print(f"🔄 [START] Analysing {symbol} | Pool: {pool_id}")

       # --- ۱. تشخیص سن توکن و انتخاب استراتژی ---
       df_1h_test = await self.analysis_engine.get_historical_data(pool_id, "hour", "1", 50)
       available_1h_data = len(df_1h_test) if df_1h_test is not None and not df_1h_test.empty else 0
       print(f"📅 [AGE CHECK] Available 1H data points for {symbol}: {available_1h_data}")

       is_new_token = available_1h_data < 24  # اگر کمتر از ۲۴ کندل ۱ ساعته داشتیم، توکن جدید است

       # --- ۲. تنظیمات و دریافت داده بر اساس نوع توکن ---
       if is_new_token:
           print(f"🆕 [STRATEGY] New token detected. Switching to Low-Timeframe mode.")
           # استراتژی برای توکن‌های جدید
           df_structure = await self.analysis_engine.get_historical_data(pool_id, "minute", "15", 100)
           df_entry = await self.analysis_engine.get_historical_data(pool_id, "minute", "5", 100)

           if df_structure is None or df_structure.empty or len(df_structure) < 20:
               print(f"❌ [FAIL-NEW] Insufficient 15M data for new token {symbol}.")
               return None
           if df_entry is None or df_entry.empty or len(df_entry) < 20:
               print(f"❌ [FAIL-NEW] Insufficient 5M data for new token {symbol}.")
               return None
        
           print(f"📊 [DATA-NEW] Received {len(df_structure)} 15M candles and {len(df_entry)} 5M candles.")
           ZONE_SCORE_MIN = 1.0 # برای توکن جدید سخت‌گیری کمتر
           VOLUME_SPIKE_MULTIPLIER = 1.5
           CANDLE_BODY_RATIO_MIN = 0.3

       else:
           print(f"📈 [STRATEGY] Mature token detected. Using Standard mode.")
           # فراخوانی مجدد برای اطمینان از وجود EMA
           df_structure = await self.analysis_engine.get_historical_data(pool_id, "hour", "1", 200)
           df_4h = await self.analysis_engine.get_historical_data(pool_id, "hour", "4", 100)
           df_entry = await self.analysis_engine.get_historical_data(pool_id, "minute", "15", 100)

           if df_4h is None or df_4h.empty or len(df_4h) < 10 or df_entry is None or df_entry.empty or len(df_entry) < 20:
               print(f"❌ [FAIL-MATURE] Insufficient data for mature token {symbol}.")
               return None
        
           print(f"📊 [DATA-MATURE] Received {len(df_structure)} 1H, {len(df_4h)} 4H, {len(df_entry)} 15M candles.")
           ZONE_SCORE_MIN = 1.5 # برای توکن بالغ کمی سخت‌گیرتر
           VOLUME_SPIKE_MULTIPLIER = 2.0
           CANDLE_BODY_RATIO_MIN = 0.4
    
       # --- ۳. منطق تحلیل یکپارچه ---
    
       # شناسایی نواحی بر روی دیتافریم ساختار (1H برای بالغ، 15M برای جدید)
       supply_zones, demand_zones = self.analysis_engine.find_major_zones(df_structure, period=5)
       print(f"🔍 [ZONES] Found {len(supply_zones)} supply zones for {symbol} on its primary timeframe.")
       await self.save_market_structure(token_address, supply_zones, 'supply')
       await self.save_market_structure(token_address, demand_zones, 'demand')

       significant_supply = [zone for zone in supply_zones if zone['score'] >= ZONE_SCORE_MIN]
       if not significant_supply:
           print(f"🔵 [INFO] No zones passed the score threshold for {symbol}.")
           return None
    
       # تایید روند (فقط برای توکن‌های بالغ)
       if not is_new_token:
           print(f"🕵️ [TREND CHECK] Checking trend for mature token {symbol}...")
           last_row = df_structure.iloc[-1]
           price = last_row['close']
    
           # اطمینان از وجود ستون‌های EMA
           if 'ema_50' not in last_row or 'ema_200' not in last_row or pd.isna(last_row['ema_50']) or pd.isna(last_row['ema_200']):
               print(f"🟡 [TREND] EMA data not available for {symbol}. Skipping trend check.")
           else:
               ema_50 = last_row['ema_50']
               ema_200 = last_row['ema_200']
        
               is_uptrend = price > ema_50 and ema_50 > ema_200
        
               if not is_uptrend:
                   print(f"❌ [TREND] Not a clear uptrend for {symbol}. Price: {price:.4f}, EMA50: {ema_50:.4f}, EMA200: {ema_200:.4f}. Signal rejected.")
                   return None
               print(f"✅ [TREND] Clear uptrend confirmed for {symbol}.")
    
       # بررسی دقیق شکست بر روی دیتافریم ورود (15M برای بالغ، 5M برای جدید)
       last_candle_entry = df_entry.iloc[-1]
       avg_volume_entry = df_entry['volume'].rolling(window=20).mean().iloc[-1]

       if pd.isna(avg_volume_entry) or avg_volume_entry <= 0: return None

       for zone in significant_supply:
           zone_price = zone['avg_price']
        
           if last_candle_entry['close'] <= zone_price: continue

           volume_ratio = last_candle_entry['volume'] / avg_volume_entry
           if volume_ratio < VOLUME_SPIKE_MULTIPLIER: continue
        
           candle_range = last_candle_entry['high'] - last_candle_entry['low']
           body_ratio = abs(last_candle_entry['close'] - last_candle_entry['open']) / candle_range if candle_range > 0 else 0
           if body_ratio < CANDLE_BODY_RATIO_MIN: continue

           print(f"🚀✅ [SUCCESS] BREAKOUT SIGNAL DETECTED for {symbol}!")
           return {
               'token_address': token_address, 'pool_id': pool_id, 'symbol': symbol,
               'signal_type': 'adaptive_breakout', 'current_price': last_candle_entry['close'],
               'resistance_level': zone_price, 'zone_score': zone['score'],
               'volume_ratio': volume_ratio, 'timestamp': datetime.now().isoformat()
           }

       print(f"🔵 [INFO] No valid breakout signal found for {symbol} in this scan.")
       return None


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

   async def has_recent_alert(self, token_address, current_price, cooldown_hours=4, price_proximity_percent=2.0):
       """
       چک می‌کند که آیا برای یک توکن در چند ساعت گذشته و در یک محدوده قیمتی مشابه، هشداری ثبت شده است یا خیر.
       """
       from datetime import datetime, timedelta

       placeholder = "%s" if db_manager.is_postgres else "?"
    
       # محاسبه آستانه قیمت
       price_threshold = (price_proximity_percent / 100.0)
       lower_bound_expr = f"{placeholder} * (1 - {placeholder})"
       upper_bound_expr = f"{placeholder} * (1 + {placeholder})"
    
       # محاسبه زمان برای دوره Cooldown
       cooldown_time_str = (datetime.now() - timedelta(hours=cooldown_hours)).isoformat()

       query = f"""
           SELECT timestamp FROM alert_history
           WHERE token_address = {placeholder}
           AND price_at_alert BETWEEN ({lower_bound_expr}) AND ({upper_bound_expr})
           AND timestamp > {placeholder}
           LIMIT 1
       """
    
       params = (token_address, current_price, price_threshold, current_price, price_threshold, cooldown_time_str)

       try:
           result = db_manager.fetchone(query, params)
           if result:
               print(f"🔵 [COOLDOWN] Recent alert found for {token_address}. Skipping.")
               return True
           return False
       except Exception as e:
           print(f"❌ Error in has_recent_alert: {e}")
           return False
