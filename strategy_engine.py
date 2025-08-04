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
        انتخاب تایم‌فریم بهینه بر اساس عمر توکن
        """
        try:
            # بررسی عمر توکن با تایم‌فریم 1 ساعته
            df_1h = await self.analysis_engine.get_historical_data(
                pool_id, "hour", "1", limit=100
            )
            hours_available = len(df_1h) if df_1h is not None and not df_1h.empty else 0
        
            if hours_available == 0:
                return None  # داده کافی وجود ندارد
            
            if hours_available < 24:  # کمتر از یک روز
                return ("minute", "5")
            elif hours_available < 72:  # کمتر از 3 روز
                return ("minute", "15")
            else:  # بیشتر از 3 روز
                return ("hour", "4")
            
        except Exception as e:
            self.logger.error(f"Error in select_optimal_timeframe: {e}")
            return ("hour", "1")  # fallback

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
        fibonacci_data = analysis_result['technical_levels']['fibonacci']
        
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
        Checks for multiple signal types using configuration from TradingConfig.
        """
        # --- استفاده از مقادیر TradingConfig ---
        ZONE_SCORE_MIN = TradingConfig.ZONE_SCORE_MIN
        PROXIMITY_THRESHOLD = TradingConfig.PROXIMITY_THRESHOLD

        # --- تحلیل نواحی مقاومت ---
        for zone in supply_zones:
            if zone['score'] < ZONE_SCORE_MIN:
                continue
            
            zone_price = zone['avg_price']
            final_score = self._calculate_confluence_score(zone, zone_price, fibonacci_data)

            if current_price < zone_price:
                proximity = (zone_price - current_price) / current_price
                if proximity < PROXIMITY_THRESHOLD:
                    return self._create_signal_dict('resistance_proximity', locals(), final_score)
            else:
                proximity_above = (current_price - zone_price) / zone_price
                if proximity_above < 0.05:
                    return self._create_signal_dict('resistance_breakout_realtime', locals(), final_score)
                elif proximity_above < PROXIMITY_THRESHOLD:
                    return self._create_signal_dict('sr_flip_retest', locals(), final_score)

        # --- تحلیل نواحی حمایت ---
        for zone in demand_zones:
            if zone['score'] < ZONE_SCORE_MIN:
                continue

            zone_price = zone['avg_price']
            proximity = abs(current_price - zone_price) / zone_price

            if proximity < PROXIMITY_THRESHOLD:
                final_score = self._calculate_confluence_score(zone, zone_price, fibonacci_data)
                return self._create_signal_dict('support_test', locals(), final_score)

        return None

    def _create_signal_dict(self, signal_type, local_vars, final_score):
        """Helper function to create a consistent signal dictionary."""
        from datetime import datetime
        zone = local_vars['zone']
        
        signal = {
            'signal_type': signal_type,
            'token_address': local_vars['token_address'],
            'pool_id': local_vars['pool_id'],
            'symbol': local_vars['symbol'],
            'current_price': local_vars['current_price'],
            'zone_score': zone['score'],
            'final_score': final_score,
            'timestamp': datetime.now().isoformat()
        }
        
        if 'resistance' in signal_type or 'breakout' in signal_type:
            signal['level_broken'] = zone['avg_price']
        elif 'support' in signal_type or 'retest' in signal_type:
            signal['support_level'] = zone['avg_price']
            
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
        query = f'''INSERT INTO alert_history (token_address, alert_type, timestamp, price_at_alert, level_price)
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
        
        current_price = df_5min['close'].iloc[-1]
        ath = df_5min['high'].max() # All-Time High در بازه دریافتی

        # --- استراتژی ۱: الگوی خرید در اولین پولبک (First Dip Buy) ---
        if len(df_5min) >= 24: # حداقل ۲ ساعت داده لازم است
            dip_from_ath = (ath - current_price) / ath if ath > 0 else 0
            
            # آیا قیمت بین ۲۰ تا ۴۰ درصد از سقف خود فاصله گرفته؟
            if 0.20 < dip_from_ath < 0.40:
                last_6_candles = df_5min.iloc[-6:] # ۳۰ دقیقه اخیر
                # آیا قیمت در ۳۰ دقیقه اخیر روند صعودی ضعیفی را شروع کرده؟
                if last_6_candles['close'].iloc[-1] > last_6_candles['close'].iloc[0]:
                    self.logger.info(f"💎 {token_info['symbol']}: Potential 'First Dip' opportunity detected.")
                    return self._create_gem_signal('GEM_FIRST_DIP', token_info, current_price, {
                        "Dip from ATH": f"{dip_from_ath:.1%}",
                        "ATH": f"${ath:.6f}"
                    }, df_5min)

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
