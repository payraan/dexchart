import asyncio
import httpx
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as patches
import pandas as pd
from datetime import datetime, timedelta
from scipy.signal import argrelextrema
import numpy as np
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CallbackQueryHandler, CommandHandler
from token_cache import TokenCache
from config import Config

BOT_TOKEN = Config.BOT_TOKEN
# Initialize token cache
token_cache = TokenCache()


def calculate_atr(df, period=14):
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

def find_major_zones(df, period=5):
    """Find major support and resistance zones"""
    if len(df) < 30:  # حداقل داده لازم
        return [], []
    
    # محاسبه ATR
    atr = calculate_atr(df, period=14)
    
    # پیدا کردن تمام فرکتال‌ها
    highs = df['high'].values
    lows = df['low'].values
    supply_fractals, demand_fractals = find_fractals(highs, lows, period=period)
    
    # محاسبه امتیاز برای هر فرکتال
    major_supply = []
    major_demand = []

    # امتیازدهی به فرکتال‌های عرضه (Supply)
    for idx in supply_fractals:
        if idx + 5 < len(df) and not pd.isna(atr.iloc[idx]):
            zone_price = df.iloc[idx]['high']
            
            # محاسبه قدرت واکنش (5 کندل بعدی)
            price_move = abs(df.iloc[idx]['high'] - df.iloc[idx+5]['close'])
            reaction_strength = price_move / atr.iloc[idx] if atr.iloc[idx] > 0 else 0
            
            # محاسبه حجم میانگین در نقطه برخورد
            volume_score = df.iloc[idx]['volume'] / df['volume'].mean() if df['volume'].mean() > 0 else 1
            
            # ذخیره اطلاعات فرکتال
            major_supply.append({
                'index': idx,
                'price': zone_price,
                'reaction_strength': reaction_strength,
                'volume_score': volume_score
            })


    # امتیازدهی به فرکتال‌های تقاضا (Demand)
    for idx in demand_fractals:
        if idx + 5 < len(df) and not pd.isna(atr.iloc[idx]):
            zone_price = df.iloc[idx]['low']
            
            # محاسبه قدرت واکنش (5 کندل بعدی)
            price_move = abs(df.iloc[idx]['low'] - df.iloc[idx+5]['close'])
            reaction_strength = price_move / atr.iloc[idx] if atr.iloc[idx] > 0 else 0
            
            # محاسبه حجم میانگین در نقطه برخورد
            volume_score = df.iloc[idx]['volume'] / df['volume'].mean() if df['volume'].mean() > 0 else 1
            
            # ذخیره اطلاعات فرکتال
            major_demand.append({
                'index': idx,
                'price': zone_price,
                'reaction_strength': reaction_strength,
                'volume_score': volume_score
            })

    # خوشه‌بندی و امتیازدهی نهایی برای Supply
    supply_clusters = []
    for zone in major_supply:
        # پیدا کردن خوشه مناسب (تلرانس 0.5%)
        found_cluster = False
        for cluster in supply_clusters:
            if abs(zone['price'] - cluster['avg_price']) / cluster['avg_price'] < 0.005:
                cluster['zones'].append(zone)
                cluster['avg_price'] = sum(z['price'] for z in cluster['zones']) / len(cluster['zones'])
                found_cluster = True
                break
        
        if not found_cluster:
            supply_clusters.append({
                'zones': [zone],
                'avg_price': zone['price']
            })

    # خوشه‌بندی و امتیازدهی نهایی برای Demand
    demand_clusters = []
    for zone in major_demand:
        # پیدا کردن خوشه مناسب (تلرانس 0.5%)
        found_cluster = False
        for cluster in demand_clusters:
            if abs(zone['price'] - cluster['avg_price']) / cluster['avg_price'] < 0.005:
                cluster['zones'].append(zone)
                cluster['avg_price'] = sum(z['price'] for z in cluster['zones']) / len(cluster['zones'])
                found_cluster = True
                break
        
        if not found_cluster:
            demand_clusters.append({
                'zones': [zone],
                'avg_price': zone['price']
            })

    # محاسبه امتیاز نهایی برای هر خوشه Supply
    for cluster in supply_clusters:
        zones = cluster['zones']
        
        # وزن‌های امتیازدهی
        avg_reaction = sum(z['reaction_strength'] for z in zones) / len(zones)
        touch_count = len(zones)
        avg_volume = sum(z['volume_score'] for z in zones) / len(zones)
        time_span = max(z['index'] for z in zones) - min(z['index'] for z in zones) + 1
        
        # امتیاز نهایی (وزن‌دار)
        final_score = (0.4 * avg_reaction) + (0.3 * touch_count) + (0.2 * avg_volume) + (0.1 * time_span/10)
        cluster['score'] = final_score
    
    # محاسبه امتیاز نهایی برای هر خوشه Demand
    for cluster in demand_clusters:
        zones = cluster['zones']
        
        avg_reaction = sum(z['reaction_strength'] for z in zones) / len(zones)
        touch_count = len(zones)
        avg_volume = sum(z['volume_score'] for z in zones) / len(zones)
        time_span = max(z['index'] for z in zones) - min(z['index'] for z in zones) + 1
        
        final_score = (0.4 * avg_reaction) + (0.3 * touch_count) + (0.2 * avg_volume) + (0.1 * time_span/10)
        cluster['score'] = final_score

    # انتخاب 2 برترین خوشه از هر نوع
    supply_clusters.sort(key=lambda x: x['score'], reverse=True)
    demand_clusters.sort(key=lambda x: x['score'], reverse=True)
    
    # برگرداندن 2 برترین از هر نوع
    top_supply = supply_clusters[:2] if len(supply_clusters) >= 2 else supply_clusters
    top_demand = demand_clusters[:2] if len(demand_clusters) >= 2 else demand_clusters
    
    return top_supply, top_demand

def draw_fibonacci_levels(ax, df, lookback_period=400):
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

async def find_geckoterminal_pool(token_address):
    """Find pool in GeckoTerminal"""
    search_url = f"https://api.geckoterminal.com/api/v2/search/pools?query={token_address}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(search_url)
        if response.status_code == 200:
            data = response.json()
            pools = data.get('data', [])
            if pools:
                # Get first pool (they're usually sorted by volume)
                best_pool = pools[0]
                pool_id = best_pool['id']  # format: network_pooladdress
                
                # Try to get symbol from relationships or use default
                try:
                    # Look for base token symbol
                    relationships = best_pool.get('relationships', {})
                    base_token = relationships.get('base_token', {}).get('data', {})
                    symbol = base_token.get('id', 'Unknown').split('_')[-1]  # Extract symbol from ID
                except:
                    symbol = "Unknown"
                
                return pool_id, symbol
    return None, None

async def get_geckoterminal_ohlcv(pool_id, timeframe="hour", aggregate="1"):
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

async def get_realtime_price(pool_id):
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

def find_fractals(highs, lows, period=5):
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

async def create_chart(pool_id, symbol, timeframe="hour", aggregate="1"):
   """Create candlestick chart from GeckoTerminal data"""
   ohlcv_list = await get_geckoterminal_ohlcv(pool_id, timeframe, aggregate)
   
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
       major_supply, major_demand = find_major_zones(df, period=5)
       
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
   realtime_price = await get_realtime_price(pool_id)
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
   draw_fibonacci_levels(ax, df)

   # Save to buffer
   img_buffer = io.BytesIO()
   plt.savefig(img_buffer, format='png', facecolor='#1a1a1a', dpi=200, bbox_inches='tight')
   img_buffer.seek(0)
   plt.close()

   return img_buffer

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    
    if len(message) == 44 and message.isalnum():
        context.user_data['token'] = message
       
        keyboard = [
            [InlineKeyboardButton("1M", callback_data="minute_1"),
             InlineKeyboardButton("5M", callback_data="minute_5"),
             InlineKeyboardButton("15M", callback_data="minute_15")],
            [InlineKeyboardButton("1H", callback_data="hour_1"),
             InlineKeyboardButton("4H", callback_data="hour_4"),
             InlineKeyboardButton("1D", callback_data="day_1")]
        ] 
       
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text("📊 Select timeframe:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Send a valid Solana token address (44 characters)")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    token_address = context.user_data.get('token')
    if not token_address:
        await query.message.reply_text("❌ Please send token address first")
        return
    
    # Parse timeframe
    timeframe_parts = query.data.split('_')
    timeframe = timeframe_parts[0]
    aggregate = timeframe_parts[1]
    
    display_name = f"{aggregate}{timeframe[0].upper()}"
    await query.message.reply_text(f"⏳ Creating {display_name} chart...")
    
    try:
        pool_id, symbol = await find_geckoterminal_pool(token_address)
        if not pool_id:
            await query.message.reply_text("❌ Token not found")
            return
        
        chart_image = await create_chart(pool_id, symbol, timeframe, aggregate)
        if chart_image:
            await query.message.reply_photo(
                photo=chart_image,
                caption=f"📊 {symbol} {display_name} Chart"
            )
        else:
            await query.message.reply_text("❌ Could not create chart")
            
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {str(e)}")

async def trending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trending command"""
    await update.message.reply_text("🔍 Fetching trending tokens...")
    
    try:
        trending_tokens = token_cache.get_trending_tokens(limit=10)
        
        if not trending_tokens:
            await update.message.reply_text("❌ No trending tokens found. Please wait for data to be collected.")
            return
        
        message = "🔥 **Top Trending Solana Tokens:**\n\n"
        
        for i, token in enumerate(trending_tokens, 1):
            symbol = token['symbol']
            price = token['price_usd']
            volume = token['volume_24h']
            
            message += f"**{i}. {symbol}**\n"
            message += f"💰 Price: ${price:.6f}\n"
            message += f"📊 24h Volume: ${volume:,.0f}\n"
            message += f"📋 `{token['address']}`\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching trending tokens: {str(e)}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(CommandHandler("trending", trending_command))
    
    print("🤖 Bot is starting...")
    
    # Background updater in separate thread
    import threading
    import time
    import asyncio
    
    def background_updater():
        print("🔄 Starting background token updates every 5 minutes...")
        while True:
            try:
                # Initial fetch on first run
                async def update():
                    tokens = await token_cache.fetch_trending_tokens()
                    print(f"✅ Background update: {len(tokens)} tokens refreshed")
                
                asyncio.run(update())
            except Exception as e:
                print(f"❌ Background update failed: {e}")
            
            # Wait 5 minutes
            time.sleep(300)
    
    # Start background thread
    bg_thread = threading.Thread(target=background_updater, daemon=True)
    bg_thread.start()
    
    print("📊 Background updates started")
    print("🚀 Bot is running...")
    
    # Start bot in main thread
    try:
        app.run_polling()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped")

if __name__ == "__main__":
    main()
