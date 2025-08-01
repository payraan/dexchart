# background_scanner.py

import asyncio
import time
from datetime import datetime
from token_cache import TokenCache
from strategy_engine import StrategyEngine
from telegram import Bot
import io
import asyncio

class BackgroundScanner:
    def __init__(self, bot_token, chat_id, scan_interval=300):
        self.token_cache = TokenCache()
        self.strategy_engine = StrategyEngine()
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        self.scan_interval = scan_interval
        self.running = False

    async def send_signal_alert(self, signal):
        """یک هشدار سیگنال همراه با نمودار را به تلگرام ارسال می‌کند."""
        try:
            # ساخت نمودار برای سیگنال
            print(f"🎨 در حال ساخت نمودار برای {signal['symbol']}...")
            chart_image = await self.strategy_engine.analysis_engine.create_chart(
                signal.get('pool_id', ''), 
                signal['symbol'], 
                timeframe="hour", 
                aggregate="1"
            )
        
            # پیام متنی
            message = (
                f"🚀 *MAJOR ZONE BREAKOUT*\n\n"
                f"**Token:** *{signal['symbol']}*\n"
                f"**Signal:** `{signal['signal_type']}`\n"
                f"**Zone Score:** `{signal['zone_score']:.1f}/10`\n"
                f"**Current Price:** `${signal['current_price']:.6f}`\n"
                f"**Level Broken:** `${signal.get('resistance_level', signal.get('support_level', 'N/A')):.6f}`\n\n"
                f"Time: `{signal['timestamp']}`"
            )
        
            if chart_image:
                # ارسال نمودار + پیام
                await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=chart_image,
                    caption=message,
                    parse_mode='Markdown'
                )
                print(f"📊 نمودار + هشدار برای {signal['symbol']} ارسال شد.")
            else:
                # فقط پیام متنی اگر نمودار ساخته نشد
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
                print(f"📱 هشدار متنی برای {signal['symbol']} ارسال شد.")
            
        except Exception as e:
            print(f"❌ خطایی در ارسال هشدار به تلگرام رخ داد: {e}")

    async def scan_tokens(self):
      """تمام توکن‌ها را برای یافتن سیگنال اسکن می‌کند."""
      print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] شروع اسکن پس‌زمینه...")

      # Get combination of trending + watchlist tokens
      trending_tokens = self.token_cache.get_trending_tokens(limit=50)
      watchlist_tokens = self.token_cache.get_watchlist_tokens(limit=150)

      # Combine both lists (trending first for priority)
      tokens = trending_tokens + watchlist_tokens

      # Remove duplicates while keeping order
      seen_addresses = set()
      unique_tokens = []
      for token in tokens:
          if token['address'] not in seen_addresses:
              seen_addresses.add(token['address'])
              unique_tokens.append(token)

      tokens = unique_tokens

      print(f"📊 اسکن {len(trending_tokens)} توکن ترند + {len(watchlist_tokens)} توکن watchlist = {len(tokens)} توکن یکتا")
   
      # DEBUG: نمایش اولین 10 توکن
      print(f"📋 لیست اولین 10 توکن برای اسکن:")
      for i, token in enumerate(tokens[:10]):
          print(f"  {i+1}. {token['symbol']} - {token['address'][:8]}...")

      if not tokens:
          print("INFO: هیچ توکنی برای اسکن یافت نشد.")
          return

      signals_found = 0
      for token in tokens:
          print(f"🔍 اسکن {token['symbol']}...")
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
              print(f"❌ خطا در اسکن {token.get('symbol', 'Unknown')}: {str(e)[:100]}")

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
