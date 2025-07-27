import asyncio
import httpx
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime
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
    
    limits = {"minute": 48, "hour": 24, "day": 30}
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

async def create_chart(pool_id, symbol, timeframe="hour", aggregate="1"):
    """Create candlestick chart from GeckoTerminal data"""
    ohlcv_list = await get_geckoterminal_ohlcv(pool_id, timeframe, aggregate)
    
    if not ohlcv_list:
        return None
    
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor('#1a1a1a')
    ax.set_facecolor('#1a1a1a')
    
    for i, candle in enumerate(ohlcv_list):
        timestamp, open_price, high, low, close, volume = candle
        color = '#00ff88' if close >= open_price else '#ff4444'
        body_height = abs(close - open_price)
        body_bottom = min(open_price, close)
        
        # Draw candlestick
        if body_height > 0:
            rect = patches.Rectangle((i-0.3, body_bottom), 0.6, body_height, 
                                   facecolor=color, edgecolor=color, alpha=0.8)
            ax.add_patch(rect)
        else:
            # Doji candle
            ax.plot([i-0.3, i+0.3], [close, close], color=color, linewidth=2)
        
        # Draw wicks
        ax.plot([i, i], [low, high], color=color, linewidth=1, alpha=0.8)
    
    # Styling
    ax.grid(True, alpha=0.3, color='#333333')
    timeframe_label = f"{aggregate}{timeframe[0].upper()}" if aggregate != "1" else timeframe.title()
    ax.set_title(f'{symbol} - {timeframe_label} Chart', color='white', fontsize=14)
    
    # Current price info
    if ohlcv_list:
        latest_candle = ohlcv_list[-1]
        latest_price = latest_candle[4]  # Close price
        
        ax.text(0.02, 0.98, f'Price: ${latest_price:.6f}', 
               transform=ax.transAxes, color='white', fontsize=12, 
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='black', alpha=0.7))
    
    # Save to buffer
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', facecolor='#1a1a1a', dpi=100, bbox_inches='tight')
    img_buffer.seek(0)
    plt.close()
    
    return img_buffer

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    
    if len(message) == 44 and message.isalnum():
        context.user_data['token'] = message
        
        keyboard = [
            [InlineKeyboardButton("15M", callback_data="minute_15"),
             InlineKeyboardButton("1H", callback_data="hour_1"),
             InlineKeyboardButton("4H", callback_data="hour_4")]
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
