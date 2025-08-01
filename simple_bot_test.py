#!/usr/bin/env python3
# simple_bot_test.py
# کد فوق ساده برای تست Railway

import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from config import Config

BOT_TOKEN = Config.BOT_TOKEN

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any message"""
    user_message = update.message.text
    await update.message.reply_text(f"✅ Bot is working! You said: {user_message}")

def main():
    print("🤖 Starting simple bot test...")
    print(f"🔑 Token starts with: {BOT_TOKEN[:10]}...")
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add message handler
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    print("🚀 Bot is running...")
    
    # Start polling (simple version)
    try:
        app.run_polling(
            drop_pending_updates=True,  # Clear any pending updates
            close_loop=False
        )
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
