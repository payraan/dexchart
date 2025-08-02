#!/usr/bin/env python3
# webhook_bot.py
# استفاده از Webhook به جای Polling برای حل مشکل Conflict

import os
from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from config import Config
import asyncio
import httpx
from contextlib import asynccontextmanager
from analysis_engine import AnalysisEngine
from background_scanner import BackgroundScanner
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler
from token_cache import TokenCache

# Configuration
BOT_TOKEN = Config.BOT_TOKEN
PORT = int(os.getenv("PORT", 8000))
print(f"🔧 Using PORT: {PORT}")

# Railway URL (use environment variable or hardcode)
RAILWAY_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN', 'dexchart-production.up.railway.app')
RAILWAY_URL = f"https://{RAILWAY_DOMAIN}"
WEBHOOK_PATH = "/webhook/telegram"  # Simplified path
WEBHOOK_URL = f"{RAILWAY_URL}{WEBHOOK_PATH}"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global scanner
    print("🚀 Application starting up...")
    
    # Try to set webhook (will fail on localhost - that's OK)
    try:
        await bot.set_webhook(url=WEBHOOK_URL)
        print(f"🔗 Webhook set to: {WEBHOOK_URL}")
    except Exception as e:
        print(f"⚠️ Webhook failed (normal for localhost): {e}")
    
    # Initialize telegram application
    await application.initialize()
    print("🤖 Telegram application initialized")
    
    scanner = BackgroundScanner(
        bot_token=BOT_TOKEN,
        chat_id=Config.CHAT_ID
    )
    asyncio.create_task(scanner.start_scanning())
    print("🔍 Background scanner started")
    
    yield
    
    # Cleanup on shutdown
    print("🛑 Shutting down...")
    if scanner:
        scanner.running = False
    await application.shutdown()
    try:
        await bot.delete_webhook()
    except:
        pass

# Create FastAPI app
app = FastAPI(lifespan=lifespan)

# Create Telegram bot
bot = Bot(token=BOT_TOKEN)
application = Application.builder().bot(bot).build()

# Background scanner instance
scanner = None

# Token cache instance  
token_cache = TokenCache()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any message"""
    user_message = update.message.text
    await update.message.reply_text(f"✅ Webhook Bot Working! You said: {user_message}")

async def chart_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle token address for chart creation"""
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

async def chart_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle timeframe button selection"""
    
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
        analysis_engine = AnalysisEngine()
        
        # Find pool and create chart
        search_url = f"https://api.geckoterminal.com/api/v2/search/pools?query={token_address}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(search_url)
            if response.status_code == 200:
                data = response.json()
                pools = data.get('data', [])
                print(f"🔍 DEBUG: Search URL: {search_url}")
                print(f"🔍 DEBUG: Found {len(pools)} pools")
                if pools:
                    best_pool = pools[0]
                    pool_id = best_pool['id']
                    
                    try:
                        relationships = best_pool.get('relationships', {})
                        base_token = relationships.get('base_token', {}).get('data', {})
                        symbol = base_token.get('id', 'Unknown').split('_')[-1]
                    except:
                        symbol = "Unknown"
                    
                    chart_image = await analysis_engine.create_chart(pool_id, symbol, timeframe, aggregate)
                    if chart_image:
                        await query.message.reply_photo(
                            photo=chart_image,
                            caption=f"📊 {symbol} {display_name} Chart"
                        )
                    else:
                        await query.message.reply_text("❌ Could not create chart")
                else:
                    await query.message.reply_text("❌ Token not found")
            else:
                await query.message.reply_text("❌ Token not found")
                print(f"❌ DEBUG: API request failed with status {response.status_code}")

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

# Add handlers
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chart_message_handler))
application.add_handler(CallbackQueryHandler(chart_button_callback))
application.add_handler(CommandHandler("trending", trending_command))



@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Webhook bot is running"}

@app.post("/webhook/telegram")
async def webhook_handler(request: Request):
    """Handle webhook updates from Telegram"""
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, bot)
        await application.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/fetch-tokens")
async def fetch_tokens():
    """Manual trigger to fetch trending tokens"""
    try:
        tokens = await token_cache.fetch_trending_tokens()
        return {"status": "success", "count": len(tokens)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/webhook-info")
async def webhook_info():
    """Check webhook status"""
    try:
        webhook_info = await bot.get_webhook_info()
        return {
            "url": webhook_info.url,
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
            "last_error_date": webhook_info.last_error_date,
            "last_error_message": webhook_info.last_error_message,
            "max_connections": webhook_info.max_connections
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    print(f"🤖 Starting webhook bot on port {PORT}")
    print(f"🔗 Webhook URL will be: {WEBHOOK_URL}")
    print(f"🔧 Railway expects port: {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
