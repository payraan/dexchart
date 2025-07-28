import asyncio
import httpx
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime, timedelta
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CallbackQueryHandler

BOT_TOKEN = "8261343183:AAE6RQHdSU54Xc86EfYFDoUtObkmT1RBBXM"

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
   
   # Set more Y-axis ticks
   ax.yaxis.set_major_locator(plt.MaxNLocator(nbins=12))
        
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

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("🤖 Fixed Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
