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
from config import Config, TradingConfig
from database_manager import db_manager
from subscription_manager import subscription_manager
from ai_analyzer import ai_analyzer
from analysis_engine import AnalysisEngine

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
    # ایجاد یک task pool برای جداسازی scanner از chart generation
    scanner_task = asyncio.create_task(scanner.start_scanning())
    app.state.scanner_task = scanner_task
    print("🔍 Background scanner started as separate task")
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

async def activate_subscription_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /activatetnt command for admins"""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    try:
        parts = context.args
        target_user_id = int(parts[0])
        sub_type = parts[1] 
        days = int(parts[1])

        subscription_manager.activate_subscription(
            user_id=target_user_id,
            subscription_type=sub_type,
            days=days,
            activated_by=user.id
        )

        await update.message.reply_text(
            f"✅ Subscription activated successfully!\n"
            f"User: {target_user_id}\n"
            f"Type: {sub_type}\n" 
            f"Duration: {days} days"
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Invalid format. Use: /activatetnt USER_ID TYPE DAYS\n"
            "Example: /activatetnt 123456 NarmoonDEX 30"
        )

async def chart_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle token address for chart creation"""
    message = update.message.text
    
    # Check subscription before processing
    user_id = update.effective_user.id
    print(f"🔍 Subscription check: user_id={user_id}, subscription={subscription}")
    subscription = subscription_manager.check_subscription(user_id)
    
    if not subscription["active"]:
        await update.message.reply_text(
            "⚠️ Access Denied\n\n"
            "You do not have an active subscription. Please contact support to activate your account."
        )
        return
    print(f"🔍 DEBUG: Received message: {message}")
    print(f"🔍 DEBUG: Message length: {len(message)}")    

    if len(message) >= 32 and len(message) <= 50:  # آدرس‌های سولانا معمولاً 32-44 کاراکتر
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
        await update.message.reply_text("Send a valid Solana token address (32-50 characters)")

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
        print(f"🔍 DEBUG: Searching for token: {token_address}")
        print(f"🔍 DEBUG: Search URL: {search_url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(search_url)
            print(f"🔍 DEBUG: API Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                pools = data.get('data', [])
                print(f"🔍 DEBUG: Found {len(pools)} pools")
                
                if pools:
                    # انتخاب بهترین pool بر اساس volume
                    best_pool = None
                    max_volume = 0
                    
                    for pool in pools:
                        try:
                            volume = float(pool.get('attributes', {}).get('volume_usd', {}).get('h24', 0))
                            if volume > max_volume:
                                max_volume = volume
                                best_pool = pool
                        except:
                            continue
                    
                    if not best_pool:
                        best_pool = pools[0]  # fallback به اولین pool
                    
                    pool_id = best_pool['id']
                    print(f"🔍 DEBUG: Selected Pool ID: {pool_id}")
                    
                    # استخراج symbol
                    symbol = "Unknown"
                    try:
                        relationships = best_pool.get('relationships', {})
                        base_token = relationships.get('base_token', {}).get('data', {})
                        if base_token:
                            symbol = base_token.get('id', '').split('_')[-1]
                        
                        # اگر symbol هنوز Unknown است، از attributes امتحان کن
                        if symbol == "Unknown" or not symbol:
                            attributes = best_pool.get('attributes', {})
                            symbol = attributes.get('name', 'Unknown').split('/')[0]
                        
                        print(f"🔍 DEBUG: Extracted Symbol: {symbol}")
                    except Exception as symbol_error:
                        print(f"⚠️ DEBUG: Symbol extraction error: {symbol_error}")
                        symbol = "Unknown"
                    
                    # تحلیل و ساخت چارت
                    print(f"🔄 DEBUG: Starting analysis for {symbol}...")
                    analysis_result = await analysis_engine.perform_full_analysis(
                        pool_id, token_address, timeframe, aggregate, symbol
                    )
                    
                    print(f"🔍 DEBUG: Analysis result exists: {analysis_result is not None}")
                    
                    if analysis_result:
                        # بررسی کیفیت داده‌ها
                        df = analysis_result.get('raw_data', {}).get('dataframe')
                        if df is not None and not df.empty:
                            print(f"🔍 DEBUG: DataFrame shape: {df.shape}")
                            print(f"🔍 DEBUG: Current price: {analysis_result.get('raw_data', {}).get('current_price')}")
                            
                            print("🎨 DEBUG: Creating chart...")
                            chart_image = await analysis_engine.create_chart(analysis_result)
                            print(f"🔍 DEBUG: Chart image exists: {chart_image is not None}")
                            
                            if chart_image:
                                await query.message.reply_photo(
                                    photo=chart_image,
                                    caption=f"📊 {symbol} {display_name} Chart"
                                )
                                print("✅ DEBUG: Chart sent successfully!")
                            else:
                                await query.message.reply_text("❌ Could not create chart - Image generation failed")
                        else:
                            await query.message.reply_text("❌ Could not create chart - No price data available")
                            print("❌ DEBUG: Empty or invalid DataFrame")
                    else:
                        await query.message.reply_text("❌ Could not create chart - Analysis failed")
                        print("❌ DEBUG: Analysis result is None")
                        
                else:
                    await query.message.reply_text("❌ Token not found in any pools")
                    print("❌ DEBUG: No pools found for this token")
            else:
                await query.message.reply_text(f"❌ API Error: {response.status_code}")
                print(f"❌ DEBUG: API request failed with status {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"❌ DEBUG: API Error details: {error_data}")
                except:
                    print(f"❌ DEBUG: API Error response: {response.text[:200]}")
    
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        await query.message.reply_text(error_msg)
        print(f"❌ DEBUG: Exception occurred: {e}")
        import traceback
        print(f"❌ DEBUG: Full traceback:\n{traceback.format_exc()}")

async def ai_analysis_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle AI analysis button click"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    subscription = subscription_manager.check_subscription(user_id)

    if not subscription['active']:
        await query.edit_message_text(text="⚠️ Access Denied. You need an active subscription for AI analysis.")
        return

    await query.edit_message_caption(caption=query.message.caption + "\n\n⏳ در حال تحلیل با هوش مصنوعی...")

    try:
        # Parse callback data: ai_analyze_{token_address}_{timeframe}_{aggregate}
        parts = query.data.split('|')
        token_address = parts[1]
        timeframe = parts[2] 
        aggregate = parts[3]

        # Find pool and create chart
        search_url = f"https://api.geckoterminal.com/api/v2/search/pools?query={token_address}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(search_url)
            if response.status_code != 200:
                await query.message.reply_text("❌ Error finding token pool for AI analysis.")
                return

            pools = response.json().get('data', [])
            if not pools:
                await query.message.reply_text("❌ Token pool not found.")
                return

            pool_id = pools[0]['id']

        # Generate chart
        analysis_engine = AnalysisEngine()
        analysis_result = await analysis_engine.perform_full_analysis(
            pool_id, token_address, timeframe, aggregate, "AI Analysis"
        )

        if not analysis_result:
            await query.message.reply_text("❌ Could not generate chart for AI analysis.")
            return

        chart_image = await analysis_engine.create_chart(analysis_result)
        chart_image_bytes = chart_image.getvalue()

        # Send to Gemini AI
        ai_response = await ai_analyzer.analyze_chart_with_gemini(chart_image_bytes)

        # Send response
        await query.message.reply_text(text=ai_response, reply_to_message_id=query.message.message_id)
        
        # Clean up loading message
        original_caption = query.message.caption.replace("\n\n⏳ در حال تحلیل با هوش مصنوعی...", "")
        await query.edit_message_caption(caption=original_caption)

    except Exception as e:
        await query.message.reply_text(f"An error occurred during AI analysis: {str(e)}")

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

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with subscription check"""
    user_id = update.effective_user.id
    
    if not subscription_manager.check_subscription(user_id):
        welcome_message = """🔒 **دسترسی محدود**

برای استفاده از ربات تحلیل توکن‌های سولانا، نیاز به فعال‌سازی اشتراک دارید.

📞 **برای فعال‌سازی:**
👈 https://t.me/Narmoonsupport

✨ **امکانات پس از فعال‌سازی:**
- اسکن ۲۴ ساعته توکن‌های ترند
- تحلیل تکنیکال پیشرفته  
- سیگنال‌های هوش مصنوعی
- نمودارهای حرفه‌ای"""
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    else:
        await update.message.reply_text(
            "🎯 **خوش آمدید!**\\n\\n"
            "📊 برای دریافت چارت، آدرس توکن سولانا را ارسال کنید\\n"
            "📈 /trending - مشاهده توکن‌های ترند", 
            parse_mode='Markdown'
        )

# Add handlers
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chart_message_handler))
application.add_handler(CallbackQueryHandler(ai_analysis_callback, pattern=r"^ai_analyze\|")) # <-- اختصاصی (به اینجا منتقل شد)
application.add_handler(CallbackQueryHandler(chart_button_callback)) # <-- عمومی
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("trending", trending_command))
application.add_handler(CommandHandler("activatetnt", activate_subscription_command))


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

@app.get("/trending-list")
async def get_trending_list():
    """Get detailed list of trending tokens"""
    try:
        trending = token_cache.get_trending_tokens(limit=50)
        
        result = []
        for i, token in enumerate(trending, 1):
            result.append({
                "rank": i,
                "symbol": token["symbol"],
                "address": token["address"][:8] + "...",  # نمایش مختصر آدرس
                "volume_24h": f"${token['volume_24h']:,.0f}",
                "price": f"${token['price_usd']:.6f}"
            })
        
        return {
            "trending_tokens": result,
            "total_count": len(trending)
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/scanner-status")
async def scanner_status():
    """Get detailed bot status including scanner health, recent signals, and cooldowns."""
    
    # --- ساخت کوئری سازگار با هر دو دیتابیس ---
    if db_manager.is_postgres:
        # کوئری برای PostgreSQL
        cooldown_check_time = "NOW() - INTERVAL '4 hours'"
        # در اینجا از type cast استفاده می‌کنیم
        timestamp_comparison = "timestamp::timestamp" 
    else:
        # کوئری برای SQLite
        cooldown_check_time = "datetime('now', '-4 hours')"
        # در اینجا از type cast استفاده نمی‌کنیم
        timestamp_comparison = "timestamp"

    last_signals_query = "SELECT * FROM alert_history ORDER BY timestamp DESC LIMIT 5"
    
    # کوئری نهایی با استفاده از متغیر ساخته می‌شود
    cooldown_query = f"""
        SELECT token_address, MAX(timestamp) as last_alert
        FROM alert_history
        WHERE {timestamp_comparison} > {cooldown_check_time}
        GROUP BY token_address
    """

    try:
        last_signals = db_manager.fetchall(last_signals_query)
        active_cooldowns = db_manager.fetchall(cooldown_query)

        return {
            "scanner_status": {
                "running": getattr(scanner, 'running', False),
                "scan_count": getattr(scanner, 'scan_count', 0),
                "last_scan_time": getattr(scanner, 'last_scan_time', None),
                "last_error": getattr(scanner, 'last_error', None)
            },
            "trading_config": {
                "zone_score_min": TradingConfig.ZONE_SCORE_MIN,
                "scan_interval_seconds": Config.SCAN_INTERVAL,
                "proximity_threshold": TradingConfig.PROXIMITY_THRESHOLD
            },
            "cooldown_info": {
                "tokens_in_cooldown": len(active_cooldowns) if active_cooldowns else 0,
                "cooldown_details": active_cooldowns
            },
            "recent_signals": last_signals
        }
    except Exception as e:
        # این لاگ برای دیباگ کردن بسیار مهم است
        logging.error(f"Error in /scanner-status endpoint: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

    try:
        last_signals = db_manager.fetchall(last_signals_query)
        active_cooldowns = db_manager.fetchall(cooldown_query)

        return {
            "scanner_status": {
                "running": getattr(scanner, 'running', False),
                "scan_count": getattr(scanner, 'scan_count', 0),
                "last_scan_time": getattr(scanner, 'last_scan_time', None),
                "last_error": getattr(scanner, 'last_error', None)
            },
            "trading_config": {
                "zone_score_min": TradingConfig.ZONE_SCORE_MIN,
                "scan_interval_seconds": Config.SCAN_INTERVAL,
                "proximity_threshold": TradingConfig.PROXIMITY_THRESHOLD
            },
            "cooldown_info": {
                "tokens_in_cooldown": len(active_cooldowns) if active_cooldowns else 0,
                "cooldown_details": active_cooldowns
            },
            "recent_signals": last_signals
        }
    except Exception as e:
        logging.error(f"Error in /scanner-status endpoint: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    print(f"🤖 Starting webhook bot on port {PORT}")
    print(f"🔗 Webhook URL will be: {WEBHOOK_URL}")
    print(f"🔧 Railway expects port: {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
