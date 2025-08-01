#!/usr/bin/env python3
# webhook_bot.py
# استفاده از Webhook به جای Polling برای حل مشکل Conflict

import os
from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from config import Config

# Configuration
BOT_TOKEN = Config.BOT_TOKEN
PORT = int(os.getenv("PORT", 8000))

# Railway URL (automatically generated)
RAILWAY_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN', 'localhost')}"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RAILWAY_URL}{WEBHOOK_PATH}"

# Create FastAPI app
app = FastAPI()

# Create Telegram bot
bot = Bot(token=BOT_TOKEN)
application = Application.builder().bot(bot).build()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any message"""
    user_message = update.message.text
    await update.message.reply_text(f"✅ Webhook Bot Working! You said: {user_message}")

# Add handler
application.add_handler(MessageHandler(filters.TEXT, handle_message))

@app.on_event("startup")
async def startup():
    """Set webhook on startup"""
    try:
        await bot.set_webhook(url=WEBHOOK_URL)
        print(f"🚀 Webhook set to: {WEBHOOK_URL}")
    except Exception as e:
        print(f"❌ Failed to set webhook: {e}")

@app.on_event("shutdown") 
async def shutdown():
    """Remove webhook on shutdown"""
    try:
        await bot.delete_webhook()
        print("🛑 Webhook deleted")
    except Exception as e:
        print(f"❌ Failed to delete webhook: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Webhook bot is running"}

@app.post(WEBHOOK_PATH)
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

if __name__ == "__main__":
    import uvicorn
    print(f"🤖 Starting webhook bot on port {PORT}")
    print(f"🔗 Webhook URL will be: {WEBHOOK_URL}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
