import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from database_manager import db_manager
from analysis_engine import AnalysisEngine
# --- بخش جدید: ایمپورت کردن تنظیمات ---
from config import TradingConfig 

class StrategyEngine:
    def __init__(self):
        self.analysis_engine = AnalysisEngine()
        # استفاده از لاگر به جای پرینت
        self.logger = logging.getLogger(__name__)
 
    async def select_optimal_timeframe(self, pool_id):
        """
        انتخاب تایم‌فریم بهینه بر اساس عمر واقعی توکن
        """
        try:
            # اول سعی می‌کنیم با داده 1 ساعته عمر رو تخمین بزنیم
            df_1h = await self.analysis_engine.get_historical_data(
                pool_id, "hour", "1", limit=500
            )
            
            if df_1h is None or df_1h.empty:
                return None, None
            
            # اگر 500 کندل 1 ساعته داریم = حداقل 20 روز عمر
            if len(df_1h) >= 500:
                # توکن قدیمی - چک کنیم چقدر قدیمیه
                df_daily = await self.analysis_engine.get_historical_data(
                    pool_id, "day", "1", limit=100
                )
                
                if df_daily is not None and len(df_daily) >= 90:
                    # بیش از 90 روز = 12H chart
                    timeframe_data = ("hour", "12")
                    self.logger.info(f"📉 Old token (90+ days) → Using 12H chart")
                elif df_daily is not None and len(df_daily) >= 30:
                    # 30-90 روز = 4H chart  
                    timeframe_data = ("hour", "4")
                    self.logger.info(f"📊 Medium age token (30-90 days) → Using 4H chart")
                else:
                    # 20-30 روز = 1H chart
                    timeframe_data = ("hour", "1")
                    self.logger.info(f"📈 Recent token (20-30 days) → Using 1H chart")
            else:
                # کمتر از 500 کندل 1 ساعته
                hours_available = len(df_1h)
                days_available = hours_available / 24
                
                if days_available < 1:  # کمتر از 1 روز
                    timeframe_data = ("minute", "5")
                    self.logger.info(f"🆕 Very new token ({hours_available}h) → Using 5M chart")
                elif days_available < 3:  # 1-3 روز
                    timeframe_data = ("minute", "15")
                    self.logger.info(f"📱 New token ({days_available:.1f} days) → Using 15M chart")
                else:  # 3-20 روز
                    timeframe_data = ("hour", "1")
                    self.logger.info(f"📈 Recent token ({days_available:.1f} days) → Using 1H chart")
            
            return timeframe_data, df_1h
            
        except Exception as e:
            self.logger.error(f"Error in select_optimal_timeframe: {e}")
            return ("hour", "4"), None

    async def detect_breakout_signal(self, analysis_result, token_address):
        """New breakout detection using pre-analyzed data"""
        if not analysis_result:
            return None
            
        metadata = analysis_result['metadata']
        symbol = metadata['symbol']
        pool_id = metadata['pool_id']
        
        self.logger.info(f"🔄 [L1-START] Analysing {symbol} using pre-computed data")
            
        current_price = analysis_result['raw_data']['current_price']
        supply_zones = analysis_result['technical_levels']['zones']['supply']
        demand_zones = analysis_result['technical_levels']['zones']['demand']
        origin_zone = analysis_result['technical_levels']['zones'].get('origin')
        fibonacci_data = analysis_result['technical_levels']['fibonacci']
        
        # بررسی Origin Zone برای توکن‌های جدید
        if origin_zone and current_price > 0:
            zone_bottom = origin_zone['zone_bottom']
            zone_top = origin_zone['zone_top']
            
            # اگر قیمت به Origin Zone برگشته
            if zone_bottom <= current_price <= zone_top * 1.1:
                self.logger.info(f"💎 {symbol}: Testing Origin Zone at ${current_price:.6f}")
                signal = {
                    'signal_type': 'ORIGIN_RETEST',
                    'token_address': token_address,
                    'pool_id': pool_id,
                    'symbol': symbol,
                    'current_price': current_price,
                    'zone_score': 10.0,  # Origin Zone همیشه امتیاز بالا
                    'final_score': 10.0,
                    'support_level': zone_bottom,
                    'timestamp': datetime.now().isoformat()
                }
                signal['analysis_result'] = analysis_result
                return signal

        signal = self._check_confluence_signals(
            current_price, supply_zones, demand_zones, fibonacci_data,
            token_address, pool_id, symbol
        )
        
        if signal:
            signal['analysis_result'] = analysis_result
            self.logger.info(f"🚀✅ [L1-SUCCESS] Signal found for {symbol}!")
            return signal
            
        self.logger.info(f"🔵 [L1-INFO] No signal found for {symbol}")
        return None

    def _check_confluence_signals(self, current_price, supply_zones, demand_zones,
                                fibonacci_data, token_address, pool_id, symbol):
        """
        Checks for signals using new zone structure
        """
        ZONE_SCORE_MIN = TradingConfig.ZONE_SCORE_MIN
        PROXIMITY_THRESHOLD = TradingConfig.PROXIMITY_THRESHOLD

        # بررسی مقاومت‌ها (Supply Zones)
        for zone in supply_zones:
            # فیلتر zones نامنطقی: supply zone باید بالاتر از قیمت باشه
            if zone['level_price'] < current_price:
                continue
            if zone.get('score', 0) < ZONE_SCORE_MIN:
                continue
        
            zone_price = zone['level_price']
            final_score = self._calculate_confluence_score(zone, zone_price, fibonacci_data)

            # فقط بعد از شکست سیگنال بده
            if current_price > zone_price:
                proximity_above = (current_price - zone_price) / zone_price
                if proximity_above < 0.08:  # تا 8% بعد از شکست
                    return self._create_signal_dict('resistance_breakout', locals(), final_score)

        # بررسی حمایت‌ها (Demand Zones)
        for zone in demand_zones:
            # فیلتر zones نامنطقی: demand zone باید پایین‌تر از قیمت باشه
            if zone['level_price'] > current_price:
                continue
            if zone.get('score', 0) < ZONE_SCORE_MIN:
                continue

            zone_price = zone['level_price']
            proximity = abs(current_price - zone_price) / zone_price

            if proximity < PROXIMITY_THRESHOLD:
                final_score = self._calculate_confluence_score(zone, zone_price, fibonacci_data)
                if final_score < 7.0:
                    continue
                return self._create_signal_dict('support_test', locals(), final_score)

        return None

    def _create_signal_dict(self, signal_type, local_vars, final_score):
       """Helper function to create a consistent signal dictionary."""
       from datetime import datetime
       zone = local_vars['zone']
       current_price = local_vars['current_price']
       zone_price = zone['level_price']

       signal = {
           'signal_type': signal_type,
           'token_address': local_vars['token_address'],
           'pool_id': local_vars['pool_id'],
           'symbol': local_vars['symbol'],
           'current_price': current_price,
           'zone_score': zone['score'],
           'final_score': final_score,
           'timestamp': datetime.now().isoformat()
       }

       # فقط level مناسب رو اضافه کن
       if 'resistance' in signal_type or 'breakout' in signal_type:
           signal['level_broken'] = zone_price
       elif 'support' in signal_type or 'retest' in signal_type:
           signal['support_level'] = zone_price

       return signal

    def _calculate_confluence_score(self, zone, zone_price, fibonacci_data):
        """Calculate confluence score between a zone and fibonacci levels."""
        zone_base_score = zone['score']
        fibonacci_bonus = 0.0
        
        if fibonacci_data and fibonacci_data.get('levels'):
            key_fib_levels = [0.382, 0.5, 0.618]
            for fib_level in key_fib_levels:
                if fib_level in fibonacci_data['levels']:
                    fib_price = fibonacci_data['levels'][fib_level]
                    # --- استفاده از مقدار TradingConfig ---
                    if abs(zone_price - fib_price) / zone_price < TradingConfig.FIBONACCI_TOLERANCE:
                        fibonacci_bonus = 2.0 # این مقدار هم می‌تواند به Config منتقل شود
                        break
        
        trend_bonus = 0.5 # این مقدار هم می‌تواند به Config منتقل شود
        
        return zone_base_score + fibonacci_bonus + trend_bonus

    async def save_alert(self, signal):
        """Save alert to the database, including the specific level price."""
        level_price = signal.get('level_broken', signal.get('support_level', 0))
        current_price = signal['current_price']
        
        if hasattr(level_price, 'item'): level_price = level_price.item()
        if hasattr(current_price, 'item'): current_price = current_price.item()
            
        level_price = float(level_price) if level_price is not None else 0.0
        current_price = float(current_price)
        
        params = (
            signal['token_address'], signal['signal_type'], signal['timestamp'],
            current_price, level_price
        )
        placeholder = "%s" if db_manager.is_postgres else "?"
        query = f'''INSERT INTO alert_history (token_address, signal_type, timestamp, price_at_alert, level_price)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})'''
        try:
            db_manager.execute(query, params)
            self.logger.info(f"💾 Alert for {signal['symbol']} at level {level_price:.6f} saved.")
        except Exception as e:
            self.logger.error(f"Error in save_alert for {signal['symbol']}: {e}")

    # کد تابع has_recent_alert که در مرحله قبل اصلاح شد، در اینجا باید قرار گیرد
    # در strategy_engine.py
    async def has_recent_alert(self, signal, cooldown_hours=None):
        """
        Checks for recent alerts. Supports dynamic cooldowns for different signal types.
        """
        from datetime import datetime, timedelta

        # --- روتر Cooldown ---
        signal_type = signal.get('signal_type', '')
       
        if signal_type.startswith('GEM_'):
            # Cooldown کوتاه‌تر برای سیگنال‌های سریع Gem
            cooldown_hours = 0.5  # 30 دقیقه
        elif cooldown_hours is None:
            # Cooldown پویا بر اساس تایم‌فریم برای سیگنال‌های تحلیل تکنیکال
            try:
                timeframe = signal['analysis_result']['metadata']['timeframe']
                if timeframe == 'minute':
                    cooldown_hours = 1
                elif timeframe == 'hour':
                    cooldown_hours = TradingConfig.COOLDOWN_HOURS
                else:  # ← این خط مفقود بود!
                    cooldown_hours = TradingConfig.COOLDOWN_HOURS
            except (KeyError, TypeError):
                # مقدار پیش‌فرض در صورت بروز خطا
                cooldown_hours = TradingConfig.COOLDOWN_HOURS

        # --- پایان روتر Cooldown ---
    
        level_price = signal.get('level_broken', signal.get('support_level'))
    
        # برای سیگنال‌های Gem که level ندارند، از خود آدرس توکن برای Cooldown استفاده می‌کنیم
        if signal_type.startswith('GEM_'):
            placeholder = "%s" if db_manager.is_postgres else "?"
            cooldown_time = (datetime.now() - timedelta(hours=cooldown_hours)).isoformat()
            query = f"""SELECT timestamp FROM alert_history 
                        WHERE token_address = {placeholder} AND signal_type = {placeholder} AND timestamp > {placeholder}
                        LIMIT 1"""
            params = (signal['token_address'], signal_type, cooldown_time)
        else:
            # منطق فعلی برای سیگنال‌های مبتنی بر سطح قیمت
            if level_price is None: return False
            if hasattr(level_price, 'item'): level_price = level_price.item()
            level_price = float(level_price)
            tolerance = 0.005
            price_min = level_price * (1 - tolerance)
            price_max = level_price * (1 + tolerance)
            cooldown_time = (datetime.now() - timedelta(hours=cooldown_hours)).isoformat()
            placeholder = "%s" if db_manager.is_postgres else "?"
            query = f"""SELECT timestamp FROM alert_history 
                        WHERE token_address = {placeholder} AND level_price BETWEEN {placeholder} AND {placeholder} AND timestamp > {placeholder}
                        LIMIT 1"""
            params = (signal['token_address'], price_min, price_max, cooldown_time)

        try:
            if db_manager.fetchone(query, params):
                self.logger.info(f"🔵 [COOLDOWN] Cooldown active for {signal['symbol']} ({signal_type}) for {cooldown_hours}h.")
                return True
            return False
        except Exception as e:
            self.logger.error(f"❌ Error in has_recent_alert for {signal['symbol']}: {e}")
            return False
 
    async def detect_gem_momentum_signal(self, df_5min, token_info):
        """استراتژی اختصاصی برای شکار توکن‌های جدید (Gem Hunter)."""
        
        # ===== کد جدید از اینجا =====
        # بررسی که توکن واقعاً جدید باشه
        if len(df_5min) > 288:  # بیشتر از 24 ساعت داده (288 کندل 5 دقیقه‌ای)
            self.logger.info(f"⏭️ {token_info['symbol']}: Too old for GEM strategy ({len(df_5min)} candles)")
            return None
        
        # بررسی که قیمت در روند صعودی کلی باشه
        if len(df_5min) > 12:  # حداقل 1 ساعت داده
            price_1h_ago = df_5min['close'].iloc[-12]
            current_price_check = df_5min['close'].iloc[-1]
            
            if current_price_check < price_1h_ago * 0.8:  # اگر بیش از 20% افت داشته
                self.logger.info(f"📉 {token_info['symbol']}: Downtrend detected, skipping GEM signal")
                return None
        # ===== پایان کد جدید =====
        
        current_price = df_5min['close'].iloc[-1]
        ath = df_5min['high'].max() # All-Time High در بازه دریافتی
        
        # --- استراتژی ۲: الگوی شکست پس از تثبیت (Consolidation Breakout) ---
        if len(df_5min) >= 12: # حداقل ۱ ساعت داده لازم است
            last_12_candles = df_5min.iloc[-12:] # یک ساعت اخیر
            high_1h = last_12_candles['high'].max()
            low_1h = last_12_candles['low'].min()
            range_pct = (high_1h - low_1h) / current_price if current_price > 0 else 0
            
            # آیا قیمت در یک ساعت گذشته در یک محدوده باریک (کمتر از ۲۰٪) تثبیت شده؟
            if range_pct < 0.20:
                # آیا قیمت در حال شکستن سقف این محدوده است؟
                if current_price >= high_1h * 0.98:
                    self.logger.info(f"💎 {token_info['symbol']}: Potential 'Consolidation Breakout' detected.")
                    return self._create_gem_signal('GEM_BREAKOUT', token_info, current_price, {
                        "Consolidation Range": f"{range_pct:.1%}"
                    }, df_5min)
        
        return None

    def _create_gem_signal(self, signal_type, token_info, price, details, df):
        """یک فرمت استاندارد برای سیگنال‌های Gem ایجاد می‌کند."""
        from datetime import datetime
        
        signal = {
            'signal_type': signal_type,
            'token_address': token_info['address'],
            'pool_id': token_info['pool_id'],
            'symbol': token_info['symbol'],
            'current_price': price,
            'details': ", ".join([f"{k}: {v}" for k, v in details.items()]),
            'timestamp': datetime.now().isoformat()
        }
        
        # اضافه کردن analysis_result برای سازگاری با تابع ارسال هشدار
        signal['analysis_result'] = {
            'metadata': {'symbol': token_info['symbol'], 'timeframe': 'minute', 'aggregate': '5'},
            'raw_data': {'dataframe': df, 'current_price': price},
            'technical_levels': {'zones': {'supply': [], 'demand': []}, 'fibonacci': None}
        }
        return signal
