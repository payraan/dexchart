# background_scanner.py

import asyncio
import time
from datetime import datetime
from token_cache import TokenCache
from strategy_engine import StrategyEngine
from telegram import Bot

class BackgroundScanner:
    def __init__(self, bot_token, chat_id, scan_interval=300):
        self.token_cache = TokenCache()
        self.strategy_engine = StrategyEngine()
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        self.scan_interval = scan_interval
        self.running = False

    async def send_signal_alert(self, signal):
        """یک هشدار سیگنال را به تلگرام ارسال می‌کند."""
        message = (
            f"🚀 *BREAKOUT ALERT*\n\n"
            f"**Token:** *{signal['symbol']}*\n"
            f"**Current Price:** `${signal['current_price']:.6f}`\n"
            f"**Resistance Broken:** `${signal['resistance_level']:.6f}`\n"
            f"**Volume:** `{signal['volume_ratio']:.1f}x normal`\n\n"
            f"Time: `{signal['timestamp']}`"
        )
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            print(f"📱 هشدار برای {signal['symbol']} به تلگرام ارسال شد.")
        except Exception as e:
            print(f"❌ خطایی در ارسال هشدار به تلگرام رخ داد: {e}")

    async def scan_tokens(self):
        """تمام توکن‌ها را برای یافتن سیگنال اسکن می‌کند."""
        print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] شروع اسکن پس‌زمینه...")
        tokens = self.token_cache.get_trending_tokens(limit=50)

        if not tokens:
            print("INFO: هیچ توکن ترندی برای اسکن یافت نشد.")
            return

        signals_found = 0
        for token in tokens:
            try:
                signal = await self.strategy_engine.detect_breakout_signal(
                    token['address'],
                    token['pool_id'],
                    token['symbol']
                )

                if signal:
                    signals_found += 1
                    # ابتدا سیگنال را در دیتابیس ذخیره کن
                    await self.strategy_engine.save_alert(signal)
                    # سپس به تلگرام ارسال کن
                    await self.send_signal_alert(signal)
                    print(f"✅ سیگنال برای {signal['symbol']} پردازش شد.")

            except Exception as e:
                print(f"❌ خطایی هنگام اسکن {token.get('symbol', 'Unknown')} رخ داد: {e}")
        
        print(f"📊 اسکن کامل شد. {signals_found} سیگنال جدید یافت شد.")

    async def start_scanning(self):
        """اسکن مداوم پس‌زمینه را آغاز می‌کند."""
        self.running = True
        print(f"🚀 اسکنر پس‌زمینه آغاز به کار کرد (هر {self.scan_interval} ثانیه).")

        while self.running:
            try:
                await self.scan_tokens()
                print(f"⏳ در حال انتظار به مدت {self.scan_interval} ثانیه تا اسکن بعدی...")
                await asyncio.sleep(self.scan_interval)
            except KeyboardInterrupt:
                self.running = False # حلقه را متوقف کن
            except Exception as e:
                print(f"❌ خطای اصلی در اسکنر: {e}")
                print("⏳ انتظار به مدت ۶۰ ثانیه به دلیل خطا...")
                await asyncio.sleep(60)
        
        print("\n🛑 اسکنر متوقف شد.")


# --- بخش اجرایی اصلی ---
async def main():
    # --- تنظیمات ---
    BOT_TOKEN = "8261343183:AAE6RQHdSU54Xc86EfYFDoUtObkmT1RBBXM"
    # آیدی عددی چت یا کانال خود را در اینجا قرار دهید
    CHAT_ID = "1951665139" 
    SCAN_INTERVAL = 300  # 5 minutes

    if CHAT_ID == "YOUR_CHAT_ID":
        print("❌ لطفا ابتدا CHAT_ID را در فایل background_scanner.py تنظیم کنید.")
        return
        
    scanner = BackgroundScanner(bot_token=BOT_TOKEN, chat_id=CHAT_ID)
    await scanner.start_scanning()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 برنامه با موفقیت خاتمه یافت.")
