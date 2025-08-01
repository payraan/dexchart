#!/usr/bin/env python3
# ultra_simple_bot.py
# بازگشت به کد اصلی اما بدون background thread

import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from config import Config

BOT_TOKEN = Config.BOT_TOKEN

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any message"""
    user_message = update.message.text
    await update.message.reply_text(f"🎉 It Works! You said: {user_message}")

def main():
    print("🚀 Ultra simple bot starting...")
    
    # Create app
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    print("🤖 Bot running...")
    
    # Simple run
    app.run_polling()

if __name__ == "__main__":
    main()
