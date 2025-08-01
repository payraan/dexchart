#!/usr/bin/env python3
# simple_polling_bot.py
# برگشت به polling با تنظیمات مناسب برای Railway

import asyncio
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from config import Config

BOT_TOKEN = Config.BOT_TOKEN

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any message"""
    user_message = update.message.text
    await update.message.reply_text(f"✅ Polling Bot Working! You said: {user_message}")

async def clear_webhook_first():
    """Clear any existing webhook before starting polling"""
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.delete_webhook()
        print("🧹 Webhook cleared successfully")
    except Exception as e:
        print(f"⚠️ Could not clear webhook: {e}")

def main():
    print("🤖 Starting simple polling bot...")
    print(f"🔑 Token starts with: {BOT_TOKEN[:10]}...")
    
    # Clear webhook first
    asyncio.run(clear_webhook_first())
    
    # Create application with specific settings for Railway
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add message handler
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    print("🚀 Bot is running with polling...")
    
    # Start polling with Railway-friendly settings
    try:
        app.run_polling(
            drop_pending_updates=True,  # Clear pending updates
            close_loop=False,
            stop_signals=None,  # Important for Railway
            allowed_updates=Update.ALL_TYPES
        )
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
