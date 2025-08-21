#!/usr/bin/env python3
import os
from fastapi import FastAPI, Request
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CallbackQueryHandler, CommandHandler
from config import Config
from contextlib import asynccontextmanager
from token_cache import TokenCache
from subscription_manager import subscription_manager
from tasks import generate_chart_task, ai_analysis_task

# Configuration
BOT_TOKEN = Config.BOT_TOKEN
PORT = int(os.getenv("PORT", 8000))
RAILWAY_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN', 'dexchart-production.up.railway.app')
WEBHOOK_URL = f"https://{RAILWAY_DOMAIN}/webhook/telegram"

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Web Service starting up...")
    
    try:
        await bot.set_webhook(url=WEBHOOK_URL)
        print(f"🔗 Webhook set to: {WEBHOOK_URL}")
    except Exception as e:
        print(f"⚠️ Webhook failed: {e}")
    
    await application.initialize()
    print("🤖 Telegram application initialized for web service")
    
    yield
    
    print("🛑 Shutting down web service...")
    await application.shutdown()
    try:
        await bot.delete_webhook()
    except:
        pass

# FastAPI & Telegram App
app = FastAPI(lifespan=lifespan)
bot = Bot(token=BOT_TOKEN)
application = Application.builder().bot(bot).build()
token_cache = TokenCache()

# --- Handlers ---
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

async def chart_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle token address for chart creation"""
    message = update.message.text
    user_id = update.effective_user.id
    
    if not subscription_manager.check_subscription(user_id):
        await update.message.reply_text("⚠️ Access Denied. You need an active subscription.")
        return

    if 32 <= len(message) <= 50:
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
    """Handle timeframe selection and queue chart generation"""
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
    
    # Immediate response to user
    await query.edit_message_text(
        f"✅ Request received! Your {display_name} chart for `{token_address}` is being generated...",
        parse_mode='Markdown'
    )
    
    # Queue the task to Celery worker
    generate_chart_task.delay(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        token_address=token_address,
        timeframe=timeframe,
        aggregate=aggregate
    )

async def ai_analysis_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle AI analysis button click"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not subscription_manager.check_subscription(user_id):
        await query.message.reply_text("⚠️ Access Denied. You need an active subscription for AI analysis.")
        return

    try:
        # Parse callback data
        parts = query.data.split('|')
        if len(parts) != 4:
            await query.message.reply_text("❌ Invalid callback format.")
            return
            
        _, token_address, timeframe, aggregate = parts
        
        # Immediate response
        current_caption = query.message.caption or ""
        await query.edit_message_caption(
            caption=current_caption + "\n\n⏳ در حال تحلیل با هوش مصنوعی..."
        )
        
        # Queue AI analysis task
        ai_analysis_task.delay(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            token_address=token_address,
            timeframe=timeframe,
            aggregate=aggregate
        )
        
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {str(e)}")

async def trending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trending command"""
    await update.message.reply_text("🔍 Fetching trending tokens...")
    
    try:
        trending_tokens = token_cache.get_trending_tokens(limit=10)
        
        if not trending_tokens:
            await update.message.reply_text("❌ No trending tokens found.")
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
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def activate_subscription_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /activatetnt command for admins"""
    user = update.effective_user
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Not authorized.")
        return

    try:
        parts = context.args
        target_user_id = int(parts[0])
        sub_type = parts[1] 
        days = int(parts[2])

        subscription_manager.activate_subscription(
            user_id=target_user_id,
            subscription_type=sub_type,
            days=days,
            activated_by=user.id
        )

        await update.message.reply_text(
            f"✅ Subscription activated!\n"
            f"User: {target_user_id}\n"
            f"Type: {sub_type}\n" 
            f"Duration: {days} days"
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Invalid format. Use: /activatetnt USER_ID TYPE DAYS"
        )

# Add handlers
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("trending", trending_command))
application.add_handler(CommandHandler("activatetnt", activate_subscription_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chart_message_handler))
application.add_handler(CallbackQueryHandler(ai_analysis_callback, pattern=r"^ai_analyze\|"))
application.add_handler(CallbackQueryHandler(chart_button_callback))

# --- Endpoints ---
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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Web service is running"}

@app.get("/trending-list")
async def get_trending_list():
    """API endpoint for trending tokens"""
    try:
        trending = token_cache.get_trending_tokens(limit=50)
        result = []
        for i, token in enumerate(trending, 1):
            result.append({
                "rank": i,
                "symbol": token["symbol"],
                "address": token["address"][:8] + "...",
                "volume_24h": f"${token['volume_24h']:,.0f}",
                "price": f"${token['price_usd']:.6f}"
            })
        
        return {"trending_tokens": result, "total_count": len(trending)}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    print(f"🤖 Starting web service on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
