import asyncio
import httpx
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
from datetime import datetime, timedelta
from scipy.signal import argrelextrema
import numpy as np
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CallbackQueryHandler, CommandHandler
from token_cache import TokenCache

BOT_TOKEN = "8261343183:AAE6RQHdSU54Xc86EfYFDoUtObkmT1RBBXM"
# Initialize token cache
token_cache = TokenCache()

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
    
    limits = {"minute": 300, "hour": 240, "day": 90}
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
   
   if data_length >= 20:
       df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
   
   if data_length >= 50:
       df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
   
   if data_length >= 100:
       df['ema_100'] = df['close'].ewm(span=100, adjust=False).mean()
   
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
   
   if 'ema_20' in df.columns and data_length >= 25:
       start_idx = 10
       ax.plot(timestamps_for_ema[start_idx:], df['ema_20'][start_idx:], color='#ff6b6b', linewidth=2, alpha=0.8, label='EMA 20')
   
   if 'ema_50' in df.columns and data_length >= 60:
       start_idx = 20
       ax.plot(timestamps_for_ema[start_idx:], df['ema_50'][start_idx:], color='#ffa726', linewidth=2, alpha=0.8, label='EMA 50')
   
   if 'ema_100' in df.columns and data_length >= 120:
       start_idx = 40
       ax.plot(timestamps_for_ema[start_idx:], df['ema_100'][start_idx:], color='#66bb6a', linewidth=2, alpha=0.8, label='EMA 100')
   
   if 'ema_200' in df.columns and data_length >= 220:  # 220 به جای 250
       start_idx = 80
       ax.plot(timestamps_for_ema[start_idx:], df['ema_200'][start_idx:], color='#42a5f5', linewidth=2, alpha=0.8, label='EMA 200')

   # ═══════════════════════════════════════════════════════════════════════════
   # 📊 SUPPLY/DEMAND ZONES DETECTION
   # ═══════════════════════════════════════════════════════════════════════════
   
   swing_length = 15
   zone_width = 0.3
   
   # Dynamic zone width based on timeframe
   if timeframe == "minute":
       zone_width = 0.5  # 0.3 → 0.5
   elif timeframe == "hour":
       zone_width = 1.5  # 1.0 → 1.5
   else:  # day
       zone_width = 2.0  # 1.5 → 2.0

   # این رو بذار:
   if timeframe == "minute":
       zone_duration_hours = int(aggregate) * 4  # 2 → 4
   elif timeframe == "hour":
       zone_duration_hours = int(aggregate) * 20  # 12 → 20
   else:  # day
       zone_duration_hours = int(aggregate) * 24 * 5  # 3 → 5
   
   half_duration = zone_duration_hours // 2
   
   if len(df) > swing_length * 2:  # Enough data for pivot detection
       highs = df['high'].values
       lows = df['low'].values
       
       # Find swing highs and lows
       high_peaks = argrelextrema(highs, np.greater, order=swing_length//2)[0]
       low_peaks = argrelextrema(lows, np.less, order=swing_length//2)[0]
       
       # Draw Supply Zones (resistance)
       for peak_idx in high_peaks[-4:]:  # Last 4 supply zones
           if peak_idx < len(df):
               zone_top = df.iloc[peak_idx]['high']
               zone_bottom = zone_top * (1 - zone_width / 100)
               peak_time = timestamps_for_ema[peak_idx]
               
               # Draw zone rectangle
               rect = patches.Rectangle((peak_time - timedelta(hours=half_duration), zone_bottom),
                                      timedelta(hours=zone_duration_hours), zone_top - zone_bottom,
                                      facecolor='red', alpha=0.25, edgecolor='red', linewidth=1)
               ax.add_patch(rect)
        
       # Draw Demand Zones (support)
       for peak_idx in low_peaks[-4:]:  # Last 4 demand zones
           if peak_idx < len(df):
               zone_bottom = df.iloc[peak_idx]['low']
               zone_top = zone_bottom * (1 + zone_width / 100)
               peak_time = timestamps_for_ema[peak_idx]
               
               # Draw zone rectangle
               rect = patches.Rectangle((peak_time - timedelta(hours=half_duration), zone_bottom),
                                      timedelta(hours=zone_duration_hours), zone_top - zone_bottom,
                                      facecolor='green', alpha=0.25, edgecolor='green', linewidth=1)
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
