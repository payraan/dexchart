import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from database_manager import db_manager
from analysis_engine import AnalysisEngine
# --- بخش جدید: ایمپورت کردن تنظیمات ---
from config import TradingConfig 
from zone_config import (
    TIER1_APPROACH_THRESHOLD, TIER1_BREAKOUT_THRESHOLD,
    TIER2_APPROACH_THRESHOLD, TIER2_BREAKOUT_THRESHOLD,
    ZONE_STATES, SIGNAL_PRIORITY
)

class StrategyEngine:
    def __init__(self):
        self.analysis_engine = AnalysisEngine()
        # استفاده از لاگر به جای پرینت
        self.logger = logging.getLogger(__name__)
 
    def get_zone_state(self, token_address, zone_price):
        """دریافت وضعیت فعلی یک zone"""
        # تبدیل numpy types به Python native
        if hasattr(zone_price, 'item'):
            zone_price = zone_price.item()
        zone_price = float(zone_price)
        
        placeholder = "%s" if db_manager.is_postgres else "?"
        query = f"""
            SELECT current_state, last_signal_time, last_price 
            FROM zone_states 
            WHERE token_address = {placeholder} 
            AND ABS(zone_price - {placeholder}) / zone_price < 0.001
        """
        result = db_manager.fetchone(query, (token_address, zone_price))
        return result if result else {'current_state': 'IDLE', 'last_price': 0}
    
    def update_zone_state(self, token_address, zone_price, new_state, signal_type, current_price):
        """آپدیت وضعیت یک zone"""
        from datetime import datetime
        
        # تبدیل numpy types
        if hasattr(zone_price, 'item'):
            zone_price = zone_price.item()
        if hasattr(current_price, 'item'):
            current_price = current_price.item()
        zone_price = float(zone_price)
        current_price = float(current_price)
        
        placeholder = "%s" if db_manager.is_postgres else "?"  # این خط مهمه!
        
        # Upsert query
        if db_manager.is_postgres:
            query = f"""
                INSERT INTO zone_states 
                (token_address, zone_price, current_state, last_signal_type, last_signal_time, last_price)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                ON CONFLICT (token_address, zone_price) 
                DO UPDATE SET 
                    current_state = EXCLUDED.current_state,
                    last_signal_type = EXCLUDED.last_signal_type,
                    last_signal_time = EXCLUDED.last_signal_time,
                    last_price = EXCLUDED.last_price,
                    updated_at = CURRENT_TIMESTAMP
            """
        else:
            query = f"""
                INSERT OR REPLACE INTO zone_states 
                (token_address, zone_price, current_state, last_signal_type, last_signal_time, last_price)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """
        
        params = (token_address, zone_price, new_state, signal_type, 
                 datetime.now().isoformat(), current_price)
        db_manager.execute(query, params)

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
        """Smart signal detection with state management"""
        if not analysis_result:
            return None
            
        metadata = analysis_result['metadata']
        symbol = metadata['symbol']
        pool_id = metadata['pool_id']
        current_price = analysis_result['raw_data']['current_price']
        
        # دریافت zones بر اساس tier
        zones = analysis_result['technical_levels']['zones']
        tier1_zones = zones.get('tier1_critical', [])
        tier2_zones = zones.get('tier2_major', [])
        
        # فقط Tier 1 و 2 رو بررسی کن
        all_important_zones = []
        
        for zone in tier1_zones:
            zone['tier'] = 'TIER1'
            all_important_zones.append(zone)
            
        for zone in tier2_zones:
            zone['tier'] = 'TIER2'
            all_important_zones.append(zone)
        
        # بررسی هر zone
        for zone in all_important_zones:
            signal = await self._check_zone_signal(
                zone, current_price, token_address, pool_id, symbol, analysis_result
            )
            if signal:
                return signal  # اولین سیگنال معتبر رو برگردون
        
        return None

    async def _check_zone_signal(self, zone, current_price, token_address, pool_id, symbol, analysis_result):
        """Check if a zone should generate a signal based on state"""
        from zone_config import (
            TIER1_APPROACH_THRESHOLD, TIER1_BREAKOUT_THRESHOLD,
            TIER2_APPROACH_THRESHOLD, TIER2_BREAKOUT_THRESHOLD
        )
        
        # تعیین zone price
        zone_price = zone.get('level_price', zone.get('zone_bottom', 0))
        if zone_price <= 0:
            return None
            
        # تعیین thresholds بر اساس tier
        if zone['tier'] == 'TIER1':
            approach_threshold = TIER1_APPROACH_THRESHOLD
            breakout_threshold = TIER1_BREAKOUT_THRESHOLD
        else:
            approach_threshold = TIER2_APPROACH_THRESHOLD
            breakout_threshold = TIER2_BREAKOUT_THRESHOLD
        
        # محاسبه فاصله
        distance = (current_price - zone_price) / zone_price
        abs_distance = abs(distance)
        
        # دریافت state قبلی
        state_info = self.get_zone_state(token_address, zone_price)
        current_state = state_info.get('current_state', 'IDLE')
        last_price = state_info.get('last_price', 0)
        
        new_state = current_state
        signal_type = None
        
        # تشخیص وضعیت جدید
        if distance > breakout_threshold and distance < 0.05:
            # قیمت بالای zone (شکست رو به بالا)
            if current_state != 'BROKEN_UP':
                new_state = 'BROKEN_UP'
                signal_type = 'resistance_breakout'
                
        elif distance < -breakout_threshold and distance > -0.05:
            # قیمت پایین zone (شکست رو به پایین)
            if current_state != 'BROKEN_DOWN':
                new_state = 'BROKEN_DOWN'
                signal_type = 'support_breakdown'
                
        elif abs_distance < approach_threshold:
            # نزدیک به zone
            if distance > 0 and current_state not in ['APPROACHING_DOWN', 'TESTING']:
                new_state = 'APPROACHING_DOWN'
                signal_type = 'approaching_support'
            elif distance < 0 and current_state not in ['APPROACHING_UP', 'TESTING']:
                new_state = 'APPROACHING_UP'
                signal_type = 'approaching_resistance'
                
        elif abs_distance > 0.05:
            # دور از zone - reset state
            if current_state != 'IDLE':
                new_state = 'IDLE'
        
        # اگر state تغییر کرد و باید سیگنال بده
        if new_state != current_state and signal_type:
            self.update_zone_state(token_address, zone_price, new_state, signal_type, current_price)
            
            return {
                'signal_type': signal_type,
                'token_address': token_address,
                'pool_id': pool_id,
                'symbol': symbol,
                'current_price': current_price,
                'zone_price': zone_price,
                'zone_tier': zone['tier'],
                'zone_score': zone.get('final_score', zone.get('score', 0)),
                'distance_percent': abs_distance * 100,
                'analysis_result': analysis_result,
                'timestamp': datetime.now().isoformat()
            }
        
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
                if final_score < 3.0:
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

    # در فایل: strategy_engine.py
    # این دو تابع را به طور کامل جایگزین تابع has_recent_alert فعلی کنید.

    def _is_signal_confident(self, signal):
        """
        یک فیلتر نهایی برای بررسی امتیاز اطمینان سیگنال.
        این تابع تصمیم می‌گیرد که آیا یک سیگنال ارزش ارسال دارد یا خیر.
        """
        signal_type = signal.get('signal_type', '')
        confidence_score = signal.get('confidence_score', 0)

        # اگر سیگنال از قبل امتیازدهی شده (مثل GEM_BREAKOUT_CONFIRMED)
        if confidence_score > 0:
            # حداقل امتیاز ۷ برای سیگنال‌های امتیازدهی شده
            is_confident = confidence_score >= 7
            if not is_confident:
                self.logger.info(f"🔵 Signal for {signal.get('symbol')} rejected. Score: {confidence_score}/10 (Threshold: 7)")
            return is_confident

        # امتیازدهی پایه برای سیگنال‌های قدیمی‌تر که هنوز سیستم امتیازدهی ندارند
        if signal_type == 'PULLBACK_RETEST_CONFIRMED':
            return True # این الگو همیشه باکیفیت است
        elif 'breakout' in signal_type:
            return True # breakout های قدیمی‌تر را فعلا عبور می‌دهیم

        # بقیه سیگنال‌های کم‌اهمیت‌تر رد می‌شوند
        self.logger.info(f"🔵 Signal for {signal.get('symbol')} ({signal_type}) rejected due to low base priority.")
        return False

    async def has_recent_alert(self, signal, cooldown_hours=None):
        """
        ابتدا امتیاز اطمینان سیگنال را بررسی می‌کند و سپس وضعیت کول‌داون را چک می‌کند.
        """
        # --- فیلتر شماره ۱: بررسی امتیاز اطمینان ---
        if not self._is_signal_confident(signal):
            return True  # True یعنی "یک هشدار اخیر وجود دارد" که باعث جلوگیری از ارسال می‌شود

        # --- فیلتر شماره ۲: بررسی کول‌داون زمانی و قیمتی (منطق قبلی) ---
        from datetime import datetime, timedelta
        signal_type = signal.get('signal_type', '')
        current_price = signal.get('current_price', 0)

        # تعیین درصد تغییر مورد نیاز برای سیگنال جدید
        if signal_type.startswith('GEM_'):
            price_change_threshold = 0.10  # 10% برای توکن‌های جدید
            min_cooldown_hours = 0.5  # حداقل 30 دقیقه
        elif 'support' in signal_type.lower():
            price_change_threshold = 0.08  # 8% برای سیگنال‌های حمایت
            min_cooldown_hours = 1.0
        else:
            price_change_threshold = 0.09  # 9% برای بقیه
            min_cooldown_hours = 2.0

        # دریافت آخرین سیگنال مشابه از دیتابیس
        placeholder = "%s" if db_manager.is_postgres else "?"
        query = f"""
            SELECT price_at_alert, timestamp
            FROM alert_history
            WHERE token_address = {placeholder}
            AND signal_type = {placeholder}
            ORDER BY timestamp DESC
            LIMIT 1
        """
        params = (signal['token_address'], signal_type)

        try:
            result = db_manager.fetchone(query, params)
            self.logger.info(f"🔍 Cooldown check for {signal.get('symbol')}: Result={result}")

            if result:
                if isinstance(result, dict):
                    last_price = float(result.get('price_at_alert', 0))
                    last_timestamp_str = result.get('timestamp', '')
                else:
                    last_price = float(result[0]) if result and result[0] else 0
                    last_timestamp_str = result[1] if result and len(result) > 1 else ''

                if not last_timestamp_str:
                    return False

                last_timestamp = datetime.fromisoformat(last_timestamp_str)
                time_passed = (datetime.now() - last_timestamp).total_seconds() / 3600

                self.logger.info(f"📊 Last: ${last_price:.10f}, Now: ${current_price:.10f}, Time: {time_passed:.1f}h")

                if last_price > 0 and current_price > 0:
                    price_change = abs(current_price - last_price) / last_price

                    # اگر قیمت به اندازه کافی تغییر نکرده و زمان کافی هم نگذشته باشد
                    if price_change < price_change_threshold and time_passed < min_cooldown_hours:
                        self.logger.info(
                            f"🔵 [COOLDOWN] {signal['symbol']} ({signal_type}): "
                            f"Price change only {price_change:.1%} (need {price_change_threshold:.1%}) "
                            f"in {time_passed:.1f}h"
                        )
                        return True # جلوگیری از ارسال

            return False  # اگر هیچ سیگنال قبلی نبود یا شرایط کول‌داون برقرار نبود

        except Exception as e:
            self.logger.error(f"❌ Error in has_recent_alert for {signal.get('symbol')}: {e}")
            return False


    async def detect_gem_momentum_signal(self, df_gem, token_info, timeframe="minute", aggregate="5"):
        """
        استراتژی اختصاصی و بازنویسی شده برای شکار توکن‌های جدید (Gem Hunter)
        با اعتبارسنجی چندلایه.
        """
        self.logger.info(f"🔍 GEM HUNTER analyzing {token_info['symbol']}...")

        # حداقل به ۲۰ کندل برای تحلیل نیاز داریم
        if df_gem is None or len(df_gem) < 20 or 'ema_50' not in df_gem.columns:
            self.logger.info(f"⏭️ Skipping {token_info['symbol']}: Insufficient data for GEM analysis.")
            return None

        current_price = df_gem['close'].iloc[-1]
        last_ema_50 = df_gem['ema_50'].iloc[-1]

        # --- فیلتر شماره ۱: بررسی روند کلی (Trend Filter) ---
        # اگر قیمت زیر EMA-50 باشد، توکن در روند صعودی نیست و ادامه نمی‌دهیم.
        if current_price < last_ema_50:
            self.logger.info(f"❌ {token_info['symbol']}: Trend is not bullish (Price < EMA50). Skipping GEM strategies.")
            return None

        analysis_result = await self.analysis_engine.perform_full_analysis(
            token_info['pool_id'], token_info['address'], timeframe, aggregate, token_info['symbol']
        )
        if not analysis_result:
            return None

        # --- استراتژی ۱: حجم انفجاری (Volume Spike) ---
        if len(df_gem) >= 10:
            current_volume = df_gem['volume'].iloc[-1]
            avg_volume = df_gem['volume'].iloc[-10:-1].mean()
            if avg_volume > 0 and current_volume > avg_volume * 4:  # حجم ۴ برابر میانگین
                self.logger.info(f"🚀 {token_info['symbol']}: Volume spike detected! Ratio: {current_volume/avg_volume:.1f}x")
                return self._create_gem_signal('GEM_VOLUME_SPIKE', token_info, current_price, {
                    "Volume Ratio": f"{current_volume/avg_volume:.1f}x"
                }, analysis_result)

        # --- استراتژی ۲: شکست پس از تثبیت (Consolidation Breakout) ---
        if len(df_gem) >= 12:
            last_12_candles = df_gem.iloc[-12:]
            high_1h = last_12_candles['high'].max()
            low_1h = last_12_candles['low'].min()
            range_pct = (high_1h - low_1h) / current_price if current_price > 0 else 0

            # شرط ۱: آیا قیمت در یک محدوده تنگ (کمتر از ۲۰٪) تثبیت شده؟
            if range_pct < 0.20:
                # شرط ۲: آیا قیمت واقعاً بالاتر از سقف محدوده شکسته است؟ (با یک حاشیه اطمینان ۳٪)
                if current_price > high_1h:
                    # شرط ۳ (تایید حجم): آیا حجم فعلی حداقل ۲ برابر میانگین است؟
                    avg_volume_range = last_12_candles['volume'].mean()
                    current_volume = df_gem['volume'].iloc[-1]
                    if avg_volume_range > 0 and current_volume >= avg_volume_range * 2:
                        self.logger.info(f"💎 {token_info['symbol']}: High-quality Consolidation Breakout detected!")
                        return self._create_gem_signal('GEM_BREAKOUT', token_info, current_price, {
                            "Consolidation Range": f"{range_pct:.1%}",
                            "Volume Ratio": f"{current_volume/avg_volume_range:.1f}x"
                        }, analysis_result)
                    else:
                        self.logger.info(f"⚠️ {token_info['symbol']}: Breakout detected but volume is too low.")

        # --- استراتژی ۳: رشد سریع قیمت (Momentum) ---
        if len(df_gem) >= 6:
            price_30m_ago = df_gem['close'].iloc[-6]
            price_growth = (current_price - price_30m_ago) / price_30m_ago if price_30m_ago > 0 else 0
            if price_growth > 0.20:  # رشد بیش از ۲۰٪ در ۳۰ دقیقه
                self.logger.info(f"🚀 {token_info['symbol']}: Rapid growth detected! {price_growth:.1%} in 30min")
                return self._create_gem_signal('GEM_MOMENTUM', token_info, current_price, {
                    "30min Growth": f"{price_growth:.1%}"
                }, analysis_result)

        self.logger.info(f"❌ {token_info['symbol']}: No valid GEM signal conditions met.")
        return None

    async def detect_pullback_retest_signal(self, analysis_result, token_address):
        """
        استراتژی پیشرفته Pullback/Retest - احتمال موفقیت بالا
        شرایط:
        1. شکست سطح مقاومت اخیر
        2. بازگشت به سطح شکسته شده (pullback)
        3. تایید حمایت در همان سطح (retest)
        """
        if not analysis_result:
            return None
            
        df = analysis_result['raw_data']['dataframe']
        current_price = analysis_result['raw_data']['current_price']
        
        if len(df) < 30:
            return None
        
        # شناسایی سطح مقاومت شکسته شده اخیر
        recent_data = df.iloc[-30:-5]
        if recent_data.empty:
            return None
            
        resistance_level = recent_data['high'].max()
        resistance_idx = recent_data['high'].idxmax()
        
        # بررسی شکست سطح
        data_after_resistance = df.iloc[resistance_idx + 1:]
        if data_after_resistance.empty or data_after_resistance['high'].max() <= resistance_level:
            return None
        
        # بررسی pullback و retest
        last_5_candles = df.iloc[-5:]
        
        # آیا قیمت به سطح مقاومت پولبک زده؟
        pullback_occurred = (last_5_candles['low'].min() <= resistance_level * 1.03) and \
                           (last_5_candles['low'].min() > resistance_level * 0.97)
        
        # آیا قیمت در حال حاضر بالاتر از سطح است؟
        successful_retest = current_price > resistance_level
        
        if pullback_occurred and successful_retest:
            confidence_score = 8  # امتیاز پایه بالا برای این الگو
            
            return {
                'signal_type': 'PULLBACK_RETEST_CONFIRMED',
                'token_address': token_address,
                'pool_id': analysis_result['metadata']['pool_id'],
                'symbol': analysis_result['metadata']['symbol'],
                'current_price': current_price,
                'zone_price': resistance_level,
                'confidence_score': confidence_score,
                'analysis_result': analysis_result,
                'timestamp': datetime.now().isoformat()
            }
        
        return None

    def _create_gem_signal(self, signal_type, token_info, price, details, analysis_result):
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
        signal['analysis_result'] = analysis_result
        return signal
