import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from database_manager import db_manager
import httpx  # اضافه شده به imports
from token_cache import TokenCache
from scipy.signal import argrelextrema
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as patches
import io
from datetime import datetime, timedelta

class AnalysisEngine:
    def __init__(self):
        self.token_cache = TokenCache()

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

                        # محاسبه EMA ها
                        if len(df) >= 50:
                            df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
                        if len(df) >= 200:
                            df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

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
        """Save indicator status to the database using the db_manager."""
        current_time = datetime.now().isoformat()
        params = (token_address, price_vs_ema200, rsi_14, macd_signal, volume_avg_20, current_time)

        if db_manager.is_postgres:
            # سینتکس صحیح PostgreSQL برای عملیات "upsert"
            query = """
                INSERT INTO indicator_status (token_address, price_vs_ema200, rsi_14, macd_signal, volume_avg_20, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (token_address) DO UPDATE SET
                    price_vs_ema200 = EXCLUDED.price_vs_ema200,
                    rsi_14 = EXCLUDED.rsi_14,
                    macd_signal = EXCLUDED.macd_signal,
                    volume_avg_20 = EXCLUDED.volume_avg_20,
                    last_updated = EXCLUDED.last_updated;
            """
        else:
            # سینتکس صحیح SQLite
            query = """
                INSERT OR REPLACE INTO indicator_status (token_address, price_vs_ema200, rsi_14, macd_signal, volume_avg_20, last_updated)
                VALUES (?, ?, ?, ?, ?, ?);
            """
        
        # اجرای کوئری با پارامترهای جداگانه برای امنیت و کارایی
        db_manager.execute(query, params)

    def calculate_atr(self, df, period=14):
        """Calculate Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        return atr

    def find_fractals(self, highs, lows, period=5):
        """پیدا کردن فرکتال‌های 5 کندلی"""
        supply_fractals = []
        demand_fractals = []
        
        half_period = period // 2
        
        for i in range(half_period, len(highs) - half_period):
            # فرکتال عرضه
            if all(highs[i] > highs[j] for j in range(i - half_period, i + half_period + 1) if j != i):
                supply_fractals.append(i)
            
            # فرکتال تقاضا
            if all(lows[i] < lows[j] for j in range(i - half_period, i + half_period + 1) if j != i):
                demand_fractals.append(i)
        
        return supply_fractals, demand_fractals

    def find_major_zones(self, df, period=5):
         """
         نواحی اصلی حمایت و مقاومت را با استفاده از یک سیستم امتیازدهی پیشرفته پیدا می‌کند.
         معیارهای امتیازدهی:
         - قدرت واکنش (Reaction Strength): حرکت قیمت پس از برخورد.
         - تعداد برخورد (Touch Count): تعداد تست‌های ناحیه.
         - حجم معاملات (Volume Score): حجم در نقاط برخورد.
         - گستره زمانی (Time Span): فاصله زمانی بین اولین و آخرین برخورد.
         """
         if len(df) < 30:
             return [], []

         atr = self.calculate_atr(df, period=14)
         avg_atr = atr.mean()
         if avg_atr == 0: return [], []

         highs = df['high']
         lows = df['low']
    
         # پیدا کردن تمام نقاط سقف و کف محلی (فرکتال‌ها)
         supply_fractals_indices, demand_fractals_indices = self.find_fractals(highs, lows, period=period)

         # --- ۱. خوشه‌بندی نواحی ---
         # خوشه‌بندی نواحی عرضه (Resistance)
         supply_clusters = []
         for idx in supply_fractals_indices:
             price = highs.iloc[idx]
             # تلرانس خوشه بر اساس ATR (پویاتر از درصد ثابت)
             cluster_tolerance = avg_atr * 0.5 
        
             found_cluster = False
             for cluster in supply_clusters:
                 if abs(price - cluster['avg_price']) < cluster_tolerance:
                     cluster['fractals'].append({'index': idx, 'price': price})
                     cluster['avg_price'] = sum(f['price'] for f in cluster['fractals']) / len(cluster['fractals'])
                     found_cluster = True
                     break
             if not found_cluster:
                 supply_clusters.append({'fractals': [{'index': idx, 'price': price}], 'avg_price': price})

         # خوشه‌بندی نواحی تقاضا (Support)
         demand_clusters = []
         for idx in demand_fractals_indices:
             price = lows.iloc[idx]
             cluster_tolerance = avg_atr * 0.5

             found_cluster = False
             for cluster in demand_clusters:
                 if abs(price - cluster['avg_price']) < cluster_tolerance:
                     cluster['fractals'].append({'index': idx, 'price': price})
                     cluster['avg_price'] = sum(f['price'] for f in cluster['fractals']) / len(cluster['fractals'])
                     found_cluster = True
                     break
             if not found_cluster:
                 demand_clusters.append({'fractals': [{'index': idx, 'price': price}], 'avg_price': price})

         # --- ۲. امتیازدهی به خوشه‌ها ---
         avg_volume = df['volume'].mean()
    
         # امتیازدهی به خوشه‌های عرضه
         for cluster in supply_clusters:
             # ۱. تعداد برخورد (هرچه بیشتر، بهتر)
             touch_count = len(cluster['fractals'])
        
             # ۲. گستره زمانی (هرچه وسیع‌تر، بهتر)
             indices = [f['index'] for f in cluster['fractals']]
             time_span = max(indices) - min(indices) if touch_count > 1 else 1

             # ۳. قدرت واکنش و حجم
             total_reaction = 0
             total_volume_score = 0
             for f in cluster['fractals']:
                 idx = f['index']
                 if idx + 5 < len(df):
                     # قدرت واکنش: قیمت چقدر بعد از ۵ کندل پایین رفته؟
                     reaction_move = highs.iloc[idx] - df['close'].iloc[idx+5]
                     total_reaction += reaction_move / atr.iloc[idx] if atr.iloc[idx] > 0 else 0
                 # امتیاز حجم: حجم در نقطه برخورد چقدر از میانگین بیشتر بوده؟
                 total_volume_score += df['volume'].iloc[idx] / avg_volume if avg_volume > 0 else 1

             avg_reaction = total_reaction / touch_count if touch_count > 0 else 0
             avg_volume_score = total_volume_score / touch_count if touch_count > 0 else 0
        
             # فرمول امتیاز نهایی (وزن‌دهی شده)
             score = (touch_count * 0.4) + (time_span * 0.1) + (avg_reaction * 0.3) + (avg_volume_score * 0.2)
             cluster['score'] = score

         # امتیازدهی به خوشه‌های تقاضا (مشابه عرضه)
         for cluster in demand_clusters:
             touch_count = len(cluster['fractals'])
             indices = [f['index'] for f in cluster['fractals']]
             time_span = max(indices) - min(indices) if touch_count > 1 else 1
        
             total_reaction = 0
             total_volume_score = 0
             for f in cluster['fractals']:
                 idx = f['index']
                 if idx + 5 < len(df):
                     reaction_move = df['close'].iloc[idx+5] - lows.iloc[idx]
                     total_reaction += reaction_move / atr.iloc[idx] if atr.iloc[idx] > 0 else 0
                 total_volume_score += df['volume'].iloc[idx] / avg_volume if avg_volume > 0 else 1
            
             avg_reaction = total_reaction / touch_count if touch_count > 0 else 0
             avg_volume_score = total_volume_score / touch_count if touch_count > 0 else 0

             score = (touch_count * 0.4) + (time_span * 0.1) + (avg_reaction * 0.3) + (avg_volume_score * 0.2)
             cluster['score'] = score
        
         # مرتب‌سازی بر اساس امتیاز و برگرداندن ۳ ناحیه برتر از هر نوع
         supply_clusters.sort(key=lambda x: x['score'], reverse=True)
         demand_clusters.sort(key=lambda x: x['score'], reverse=True)
    
         return supply_clusters[:3], demand_clusters[:3]


    async def get_geckoterminal_ohlcv(self, pool_id, timeframe="hour", aggregate="1"):
        """Get OHLCV from GeckoTerminal"""
        network, pool_address = pool_id.split('_')
        url = f"https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}/ohlcv/{timeframe}"
            
        limits = {"minute": 300, "hour": 1000, "day": 90}  # بازگردوندن به حالت قبل
        params = {
            'aggregate': aggregate,
            'limit': str(limits.get(timeframe, 24))
        }
            
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get('data', {}).get('attributes', {}).get('ohlcv_list', [])
        return None

    async def get_realtime_price(self, pool_id):
        """Get real-time price from GeckoTerminal"""
        network, pool_address = pool_id.split('_')
        url = f"https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}"
            
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                pool_data = data.get('data', {})
                attributes = pool_data.get('attributes', {})
                return float(attributes.get('base_token_price_usd', 0))
        return None
            
    def draw_fibonacci_levels(self, ax, df, lookback_period=400):
        """Draw Fibonacci retracement levels based on highest/lowest in lookback period"""
        if len(df) < lookback_period:
            lookback_period = len(df)
            
        # برش دیتافریم - آخرین کندل‌ها
        recent_df = df.iloc[-lookback_period:]
            
        # یافتن سقف و کف مطلق
        high_point = recent_df['high'].max()
        low_point = recent_df['low'].min()
            
        # محاسبه اختلاف قیمت
        price_range = high_point - low_point
            
        if price_range <= 0:
            return  # اگه range نداشتیم، چیزی رسم نکن
                
        # سطوح فیبوناچی استاندارد
        fib_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        fib_colors = ['#e74c3c', '#ff9ff3', '#54a0ff', '#5f27cd', '#00d2d3', '#ff9f43', '#2ecc71']

        # رسم هر سطح فیبوناچی
        for i, level in enumerate(fib_levels):
            level_price = high_point - (price_range * level)
            
            # رسم خط افقی
            ax.axhline(y=level_price, color=fib_colors[i], linestyle='--',
                      linewidth=1, alpha=0.7)
            
            # اضافه کردن برچسب
            ax.text(0.02, level_price, f'Fib {level}: ${level_price:.6f}',
                   transform=ax.get_yaxis_transform(),
                   verticalalignment='center', fontsize=9,
                   color=fib_colors[i], alpha=0.8,
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))

    async def create_chart(self, pool_id, symbol, timeframe="hour", aggregate="1"):
        """Create candlestick chart from GeckoTerminal data"""
        ohlcv_list = await self.get_geckoterminal_ohlcv(pool_id, timeframe, aggregate)

        if not ohlcv_list:
            return None

        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(16, 9))
        fig.patch.set_facecolor('#1a1a1a')
        ax.set_facecolor('#1a1a1a')

        # Calculate candle width based on timeframe
        if timeframe == "minute":
            candle_width = timedelta(minutes=int(aggregate))
        elif timeframe == "hour":
            candle_width = timedelta(hours=int(aggregate))
        else:  # day
            candle_width = timedelta(days=int(aggregate))

        # Convert to matplotlib time units (80% of full width for spacing)
        width_delta = candle_width * 0.8

        timestamps = []

        # Convert OHLCV data to pandas DataFrame for EMA calculations
        data_list = []
        for candle in ohlcv_list:
            timestamp, open_price, high, low, close, volume = candle
            data_list.append({
                'timestamp': timestamp,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })

        df = pd.DataFrame(data_list)

        # Sort by timestamp for correct EMA calculation
        df = df.sort_values('timestamp').reset_index(drop=True)

        # Calculate EMAs (only if enough data available)
        data_length = len(df)

        if data_length >= 50:
            df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

        if data_length >= 200:
            df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

        for candle in ohlcv_list:
            timestamp, open_price, high, low, close, volume = candle
            dt_timestamp = datetime.fromtimestamp(timestamp)
            timestamps.append(dt_timestamp)

            # محاسبه مرکز افقی کندل
            candle_center = dt_timestamp + (width_delta / 2)

            color = '#00ff88' if close >= open_price else '#ff4444'
            body_height = abs(close - open_price)
            body_bottom = min(open_price, close)

            # Draw wicks (سایه) - اول سایه رسم می‌شه
            ax.plot([candle_center, candle_center], [low, high], color=color, linewidth=2, alpha=0.9)

            # Draw candlestick body (بدنه)
            if body_height > 0:
                rect = patches.Rectangle((dt_timestamp, body_bottom), width_delta, body_height,
                                       facecolor=color, edgecolor=color, alpha=0.8)
                ax.add_patch(rect)
            else:
                # Doji candle
                ax.plot([dt_timestamp, dt_timestamp + width_delta], [close, close], color=color, linewidth=2)

        # Draw EMA lines (only if calculated and have enough warm-up period)
        timestamps_for_ema = [datetime.fromtimestamp(ts) for ts in df['timestamp']]

        if 'ema_50' in df.columns and data_length >= 60:
            start_idx = 20
            ax.plot(timestamps_for_ema[start_idx:], df['ema_50'][start_idx:], color='#ffa726', linewidth=2, alpha=0.8, label='EMA 50')

        if 'ema_200' in df.columns and data_length >= 220:  # 220 به جای 250
            start_idx = 80
            ax.plot(timestamps_for_ema[start_idx:], df['ema_200'][start_idx:], color='#42a5f5', linewidth=2, alpha=0.8, label='EMA 200')

        # ═══════════════════════════════════════════════════════════════════════════
        # 📊 SUPPLY/DEMAND ZONES DETECTION
        # ═══════════════════════════════════════════════════════════════════════════
            
        # امتداد ناحیه به سمت راست برای ظاهر بهتر (همیشه تعریف شه)
        chart_end_time = timestamps_for_ema[-1] + (timestamps_for_ema[-1] - timestamps_for_ema[0]) * 0.1
   
        if len(df) > 30:  # حداقل داده برای Major zones
            # پیدا کردن سطوح ماژور
            major_supply, major_demand = self.find_major_zones(df, period=5)
   
            # Draw Major Supply Zones (resistance)
            for cluster in major_supply:
                zone_top = cluster['avg_price']
                zone_bottom = zone_top * (1 - 0.005)  # 0.5% thickness
   
                start_num = mdates.date2num(timestamps_for_ema[0])
                end_num = mdates.date2num(chart_end_time)
                width_num = end_num - start_num
   
                rect = patches.Rectangle((start_num, zone_bottom), width_num, zone_top - zone_bottom,
                                        facecolor='orange', alpha=0.25, edgecolor='orange', linewidth=2)
                ax.add_patch(rect)
       
            # Draw Major Demand Zones (support)
            for cluster in major_demand:
                zone_bottom = cluster['avg_price']
                zone_top = zone_bottom * (1 + 0.005)  # 0.5% thickness
   
                start_num = mdates.date2num(timestamps_for_ema[0])
                end_num = mdates.date2num(chart_end_time)
                width_num = end_num - start_num
   
                rect = patches.Rectangle((start_num, zone_bottom), width_num, zone_top - zone_bottom,
                                        facecolor='purple', alpha=0.25, edgecolor='purple', linewidth=2)
                ax.add_patch(rect)
       
        # Styling
        ax.grid(True, alpha=0.3, color='#333333')
        timeframe_label = f"{aggregate}{timeframe[0].upper()}" if aggregate != "1" else timeframe.title()
        ax.set_title(f'{symbol} - {timeframe_label} Chart', color='white', fontsize=14)
        # Add watermark
        ax.text(0.98, 0.95, 'NarmoonAI',
               transform=ax.transAxes, color='#999999', fontsize=16,
               alpha=0.8, ha='right', va='top',
               style='italic', weight='light')
                    
        # Current price info
        realtime_price = await self.get_realtime_price(pool_id)
        if realtime_price:
           latest_price = realtime_price
        elif ohlcv_list:
           latest_price = ohlcv_list[-1][4]  # Fallback to last candle
        else:
           latest_price = 0

        if latest_price > 0:  
           ax.text(0.02, 0.98, f'Price: ${latest_price:.6f}',
                  transform=ax.transAxes, color='white', fontsize=12,
                  verticalalignment='top',
                  bbox=dict(boxstyle='round', facecolor='black', alpha=0.7))
       
        # تنظیم محدوده محور X برای اطمینان 
        ax.set_xlim(timestamps_for_ema[0], chart_end_time)
       
        # رسم سطوح فیبوناچی
        self.draw_fibonacci_levels(ax, df)
       
        # Save to buffer
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', facecolor='#1a1a1a', dpi=200, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close()
    
        return img_buffer

