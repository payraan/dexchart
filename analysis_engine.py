import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from database_manager import db_manager
import httpx
from token_cache import TokenCache
from scipy.signal import argrelextrema
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as patches
import io

class AnalysisEngine:
    def __init__(self):
        self.token_cache = TokenCache()
        # In-Memory Cache for analysis results
        self.analysis_cache = {}
        self.cache_duration = 60  # 60 seconds cache validity

    def _is_cache_valid(self, cache_key):
        """Check if cached analysis is still valid"""
        from datetime import datetime, timedelta
        if cache_key not in self.analysis_cache:
            return False
        
        cached_time = self.analysis_cache[cache_key].get('cached_at')
        if not cached_time:
            return False
            
        return datetime.now() - cached_time < timedelta(seconds=self.cache_duration)

    async def perform_full_analysis(self, pool_id, timeframe="hour", aggregate="1", symbol=""):
        """Main analysis function - Single Source of Truth"""
        from datetime import datetime
        
        cache_key = f"{pool_id}_{timeframe}_{aggregate}"
        
        # Check cache first
        if self._is_cache_valid(cache_key):
            print(f"✅ [CACHE] Using cached result for {pool_id}")
            return self.analysis_cache[cache_key]['result']
        
        # Perform full analysis
        analysis_result = await self._do_full_analysis(pool_id, timeframe, aggregate, symbol)
        
        if analysis_result and self._validate_analysis_result(analysis_result):
            # Cache the result
            self.analysis_cache[cache_key] = {
                'result': analysis_result,
                'cached_at': datetime.now()
            }
            return analysis_result
            
        return None

    def _validate_analysis_result(self, analysis_result):
        """Validate analysis result structure and data quality"""
        if not analysis_result or not isinstance(analysis_result, dict):
            return False
            
        required_keys = ['metadata', 'raw_data', 'technical_levels']
        if not all(key in analysis_result for key in required_keys):
            return False
            
        # Check dataframe quality
        df = analysis_result['raw_data'].get('dataframe')
        if df is None or df.empty or len(df) < 30:
            return False
            
        return True

    async def _do_full_analysis(self, pool_id, timeframe, aggregate, symbol):
        """Core analysis logic - computes all technical data"""
        from datetime import datetime
        
        # Get historical data
        df = await self.get_historical_data(pool_id, timeframe, aggregate, limit=500)
        if df is None or df.empty or len(df) < 30:
            return None
            
        # Calculate zones
        supply_zones, demand_zones = self.find_major_zones(df, period=5)
            
        # Calculate fibonacci
        fibonacci_data = self._calculate_fibonacci_levels(df)
            
        # Get current price
        current_price = df['close'].iloc[-1]
            
        # Build analysis result
        analysis_result = {
            'metadata': {
                'pool_id': pool_id,
                'symbol': symbol,
                'timeframe': timeframe,
                'aggregate': aggregate,
                'timestamp': datetime.now().isoformat()
            },
            'raw_data': {
                'dataframe': df,
                'current_price': current_price
            },
            'technical_levels': {
                'zones': {
                    'supply': supply_zones,
                    'demand': demand_zones
                },
                'fibonacci': fibonacci_data,
                'moving_averages': {
                    'ema_50': df['ema_50'].iloc[-1] if 'ema_50' in df.columns and not pd.isna(df['ema_50'].iloc[-1]) else None,
                    'ema_200': df['ema_200'].iloc[-1] if 'ema_200' in df.columns and not pd.isna(df['ema_200'].iloc[-1]) else None
                }
            },
            'signal_context': {}
        }
            
        return analysis_result

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

                        if len(df) >= 50:
                            df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
                        if len(df) >= 200:
                            df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

                        return df
        except Exception as e:
            print(f"Error fetching historical data: {e}")

        return pd.DataFrame()

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
            if all(highs[i] > highs[j] for j in range(i - half_period, i + half_period + 1) if j != i):
                supply_fractals.append(i)
            
            if all(lows[i] < lows[j] for j in range(i - half_period, i + half_period + 1) if j != i):
                demand_fractals.append(i)
        
        return supply_fractals, demand_fractals

    def find_major_zones(self, df, period=5):
         if len(df) < 30:
             return [], []

         atr = self.calculate_atr(df, period=14)
         avg_atr = atr.mean()
         if pd.isna(avg_atr) or avg_atr == 0: return [], []

         highs = df['high']
         lows = df['low']
    
         supply_fractals_indices, demand_fractals_indices = self.find_fractals(highs, lows, period=period)

         supply_clusters = []
         for idx in supply_fractals_indices:
             price = highs.iloc[idx]
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

         avg_volume = df['volume'].mean()
    
         for cluster in supply_clusters:
             touch_count = len(cluster['fractals'])
             indices = [f['index'] for f in cluster['fractals']]
             time_span = max(indices) - min(indices) if touch_count > 1 else 1
             total_reaction = 0
             total_volume_score = 0
             for f in cluster['fractals']:
                 idx = f['index']
                 if idx + 5 < len(df):
                     reaction_move = highs.iloc[idx] - df['close'].iloc[idx+5]
                     atr_val = atr.iloc[idx] if not pd.isna(atr.iloc[idx]) else avg_atr
                     total_reaction += reaction_move / atr_val if atr_val > 0 else 0
                 total_volume_score += df['volume'].iloc[idx] / avg_volume if avg_volume > 0 else 1
             avg_reaction = total_reaction / touch_count if touch_count > 0 else 0
             avg_volume_score = total_volume_score / touch_count if touch_count > 0 else 0
             score = (touch_count * 0.4) + (time_span * 0.1) + (avg_reaction * 0.3) + (avg_volume_score * 0.2)
             cluster['score'] = score

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
                     atr_val = atr.iloc[idx] if not pd.isna(atr.iloc[idx]) else avg_atr
                     total_reaction += reaction_move / atr_val if atr_val > 0 else 0
                 total_volume_score += df['volume'].iloc[idx] / avg_volume if avg_volume > 0 else 1
             avg_reaction = total_reaction / touch_count if touch_count > 0 else 0
             avg_volume_score = total_volume_score / touch_count if touch_count > 0 else 0
             score = (touch_count * 0.4) + (time_span * 0.1) + (avg_reaction * 0.3) + (avg_volume_score * 0.2)
             cluster['score'] = score
        
         supply_clusters.sort(key=lambda x: x['score'], reverse=True)
         demand_clusters.sort(key=lambda x: x['score'], reverse=True)
    
         return supply_clusters[:3], demand_clusters[:3]

    def _calculate_fibonacci_levels(self, df, lookback_period=400):
        """Calculate Fibonacci retracement levels (computation only)"""
        if len(df) < lookback_period:
            lookback_period = len(df)
        
        recent_df = df.iloc[-lookback_period:]
        high_point = recent_df['high'].max()
        low_point = recent_df['low'].min()
        price_range = high_point - low_point
        
        if price_range <= 0 or pd.isna(price_range):
            return None
            
        fib_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        levels_dict = {}
        
        for level in fib_levels:
            level_price = high_point - (price_range * level)
            levels_dict[level] = level_price
            
        return {
            'levels': levels_dict,
            'high_point': high_point,
            'low_point': low_point,
            'price_range': price_range
        }

    def draw_fibonacci_levels(self, ax, fib_data):
        """Draw Fibonacci retracement levels based on pre-calculated data"""
        if not fib_data:
            return

        levels = fib_data['levels']
        fib_colors = ['#e74c3c', '#ff9ff3', '#54a0ff', '#5f27cd', '#00d2d3', '#ff9f43', '#2ecc71']
        
        for i, (level_key, level_price) in enumerate(levels.items()):
            ax.axhline(y=level_price, color=fib_colors[i], linestyle='--',
                       linewidth=1, alpha=0.7)
            
            ax.text(0.02, level_price, f'Fib {level_key:.3f}: ${level_price:.6f}',
                   transform=ax.get_yaxis_transform(),
                   verticalalignment='center', fontsize=9,
                   color=fib_colors[i], alpha=0.8,
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))

    async def create_chart(self, analysis_result):
        """Create candlestick chart from pre-analyzed data"""
        if not analysis_result:
            return None

        df = analysis_result['raw_data']['dataframe']
        metadata = analysis_result['metadata']
        technical_levels = analysis_result['technical_levels']
        symbol = metadata['symbol']
        
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(16, 9))
        fig.patch.set_facecolor('#1a1a1a')
        ax.set_facecolor('#1a1a1a')

        timeframe = metadata['timeframe']
        aggregate = metadata['aggregate']

        if timeframe == "minute":
            candle_width = timedelta(minutes=int(aggregate))
        elif timeframe == "hour":
            candle_width = timedelta(hours=int(aggregate))
        else:
            candle_width = timedelta(days=int(aggregate))
        
        width_delta = candle_width * 0.8
        timestamps = [datetime.fromtimestamp(ts) for ts in df['timestamp']]

        for i, row in df.iterrows():
            dt_timestamp = timestamps[i]
            open_price, high, low, close = row['open'], row['high'], row['low'], row['close']
            
            candle_center = dt_timestamp + (width_delta / 2)
            color = '#00ff88' if close >= open_price else '#ff4444'
            body_height = abs(close - open_price)
            body_bottom = min(open_price, close)

            ax.plot([candle_center, candle_center], [low, high], color=color, linewidth=2, alpha=0.9)

            if body_height > 0:
                rect = patches.Rectangle((dt_timestamp, body_bottom), width_delta, body_height,
                                       facecolor=color, edgecolor=color, alpha=0.8)
                ax.add_patch(rect)
            else:
                ax.plot([dt_timestamp, dt_timestamp + width_delta], [close, close], color=color, linewidth=2)

        if 'ema_50' in df.columns and not df['ema_50'].isnull().all():
            ax.plot(timestamps, df['ema_50'], color='#ffa726', linewidth=2, alpha=0.8, label='EMA 50')

        if 'ema_200' in df.columns and not df['ema_200'].isnull().all():
            ax.plot(timestamps, df['ema_200'], color='#42a5f5', linewidth=2, alpha=0.8, label='EMA 200')

        chart_end_time = timestamps[-1] + (timestamps[-1] - timestamps[0]) * 0.1
   
        major_supply = technical_levels['zones']['supply']
        major_demand = technical_levels['zones']['demand']

        for cluster in major_supply:
            zone_top = cluster['avg_price']
            zone_bottom = zone_top * (1 - 0.005)
            start_num = mdates.date2num(timestamps[0])
            end_num = mdates.date2num(chart_end_time)
            width_num = end_num - start_num
            rect = patches.Rectangle((start_num, zone_bottom), width_num, zone_top - zone_bottom,
                                    facecolor='orange', alpha=0.25, edgecolor='orange', linewidth=2)
            ax.add_patch(rect)
   
        for cluster in major_demand:
            zone_bottom = cluster['avg_price']
            zone_top = zone_bottom * (1 + 0.005)
            start_num = mdates.date2num(timestamps[0])
            end_num = mdates.date2num(chart_end_time)
            width_num = end_num - start_num
            rect = patches.Rectangle((start_num, zone_bottom), width_num, zone_top - zone_bottom,
                                    facecolor='purple', alpha=0.25, edgecolor='purple', linewidth=2)
            ax.add_patch(rect)
       
        ax.grid(True, alpha=0.3, color='#333333')
        timeframe_label = f"{aggregate}{timeframe[0].upper()}" if aggregate != "1" else timeframe.title()
        ax.set_title(f'{symbol} - {timeframe_label} Chart', color='white', fontsize=14)
        ax.text(0.98, 0.95, 'NarmoonAI',
               transform=ax.transAxes, color='#999999', fontsize=16,
               alpha=0.8, ha='right', va='top',
               style='italic', weight='light')
                    
        latest_price = analysis_result['raw_data']['current_price']
        if latest_price > 0:  
           ax.text(0.02, 0.98, f'Price: ${latest_price:.6f}',
                  transform=ax.transAxes, color='white', fontsize=12,
                  verticalalignment='top',
                  bbox=dict(boxstyle='round', facecolor='black', alpha=0.7))
       
        ax.set_xlim(timestamps[0], chart_end_time)
       
        self.draw_fibonacci_levels(ax, technical_levels['fibonacci'])
       
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', facecolor='#1a1a1a', dpi=200, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close()
    
        return img_buffer
