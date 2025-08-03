# background_scanner.py

import asyncio
import time
from datetime import datetime
from token_cache import TokenCache
from strategy_engine import StrategyEngine
from telegram import Bot
import io
import asyncio
from config import Config

class BackgroundScanner:
    def __init__(self, bot_token, chat_id, scan_interval=120):
        self.token_cache = TokenCache()
        self.strategy_engine = StrategyEngine()
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        self.scan_interval = scan_interval
        self.running = False

    async def send_signal_alert(self, signal):
        """یک هشدار سیگنال همراه با نمودار را به تلگرام ارسال می‌کند."""
        try:
            # استخراج اطلاعات از سیگنال آماده
            analysis_result = signal.get('analysis_result')
            symbol = signal['symbol']
            
            print(f"🎨 در حال ساخت نمودار برای {symbol}...")
            
            # ساخت نمودار از روی تحلیل آماده
            chart_image = await self.strategy_engine.analysis_engine.create_chart(
                analysis_result
            )
        
            # ساخت پیام
            message = (
                f"🚀 *MAJOR ZONE BREAKOUT*\n\n"
                f"**Token:** *{signal['symbol']}*\n"
                f"**Signal:** `{signal['signal_type']}`\n"
                f"**Zone Score:** `{signal.get('zone_score', 0):.1f}/10`\n"
                f"**Final Score:** `{signal.get('final_score', 0):.1f}/10`\n"
                f"**Current Price:** `${signal['current_price']:.6f}`\n"
                f"**Level Broken:** `${signal.get('level_broken', signal.get('support_level', 'N/A')):.6f}`\n\n"
                f"Time: `{signal['timestamp']}`"
            )
        
            if chart_image:
                await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=chart_image,
                    caption=message,
                    parse_mode='Markdown'
                )
                print(f"📊 نمودار + هشدار برای {symbol} ارسال شد.")
            else:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
                print(f"📱 هشدار متنی برای {symbol} ارسال شد.")
            
        except Exception as e:
            print(f"❌ خطایی در ارسال هشدار به تلگرام رخ داد: {e}")


    async def scan_tokens(self):
      """تمام توکن‌ها را برای یافتن سیگنال اسکن می‌کند (با معماری جدید و تایم‌فریم پویا)."""
      print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] شروع اسکن پس‌زمینه...")

      trending_tokens = self.token_cache.get_trending_tokens(limit=50)
      watchlist_tokens = self.token_cache.get_watchlist_tokens(limit=150)
      tokens = trending_tokens + watchlist_tokens
      
      seen_addresses = set()
      unique_tokens = [t for t in tokens if t['address'] not in seen_addresses and not seen_addresses.add(t['address'])]

      print(f"📊 اسکن {len(trending_tokens)} توکن ترند + {len(watchlist_tokens)} توکن watchlist = {len(unique_tokens)} توکن یکتا")

      if not unique_tokens:
          print("INFO: هیچ توکنی برای اسکن یافت نشد.")
          return

      signals_found = 0
      for token in unique_tokens:
          print(f"🔍 اسکن {token['symbol']}...")
          try:
              # قدم ۱: تشخیص وضعیت توکن (جدید یا بالغ)
              df_test = await self.strategy_engine.analysis_engine.get_historical_data(token['pool_id'], "hour", "1", 50)
              is_new_token = df_test.empty or len(df_test) < 48

              if is_new_token:
                  print(f"🆕 [STRATEGY] New token detected. Using 15m timeframe.")
                  timeframe, aggregate = "minute", "15"
              else:
                  print(f"📈 [STRATEGY] Mature token detected. Using 1h timeframe.")
                  timeframe, aggregate = "hour", "1"

              # قدم ۲: انجام تحلیل کامل با تایم‌فریم پویا
              analysis_result = await self.strategy_engine.analysis_engine.perform_full_analysis(
                  token['pool_id'],
                  timeframe=timeframe,
                  aggregate=aggregate,
                  symbol=token['symbol']
              )

              if not analysis_result:
                  print(f"🔵 [INFO] تحلیل معتبری برای {token['symbol']} یافت نشد.")
                  continue

              # قدم ۳: ارسال نتیجه تحلیل به موتور استراتژی
              signal = await self.strategy_engine.detect_breakout_signal(
                  analysis_result,
                  token['address']
              )

              if signal:
                  is_recent = await self.strategy_engine.has_recent_alert(signal)
    
                  if not is_recent:
                      signals_found += 1
                      await self.strategy_engine.save_alert(signal)
                      await self.send_signal_alert(signal)
                      print(f"✅ سیگنال برای {signal['symbol']} پردازش شد.")
                  else:
                      print(f"🔵 سیگنال {signal['symbol']} به دلیل cooldown رد شد.")

          except Exception as e:
              print(f"❌ خطا در اسکن {token.get('symbol', 'Unknown')}: {str(e)[:150]}")

      print(f"📊 اسکن کامل شد. {signals_found} سیگنال جدید یافت شد.")


    async def start_scanning(self):
        """اسکن مداوم پس‌زمینه را آغاز می‌کند."""
        self.running = True
        print(f"🚀 اسکنر پس‌زمینه آغاز به کار کرد (هر {self.scan_interval} ثانیه).")

        # --- قدم جدید: دریافت اولیه توکن‌ها برای پر کردن دیتابیس خالی ---
        print("🔄 در حال دریافت لیست اولیه توکن‌ها برای پر کردن دیتابیس...")
        try:
            initial_tokens = await self.token_cache.fetch_trending_tokens()
            if initial_tokens:
                print(f"✅ لیست اولیه با {len(initial_tokens)} توکن دریافت و در دیتابیس ذخیره شد.")
            else:
                print("⚠️ لیست اولیه توکن‌ها دریافت نشد.")
        except Exception as e:
            print(f"❌ خطا در دریافت لیست اولیه توکن‌ها: {e}")
        # ---------------------------------------------------------

        while self.running:
            try:
                await self.scan_tokens()
                print(f"⏳ در حال انتظار به مدت {self.scan_interval} ثانیه تا اسکن بعدی...")
                await asyncio.sleep(self.scan_interval)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f"❌ خطای اصلی در اسکنر: {e}")
                print("⏳ انتظار به مدت ۶۰ ثانیه به دلیل خطا...")
                await asyncio.sleep(60)
        
        print("\n🛑 اسکنر متوقف شد.")


# --- بخش اجرایی اصلی ---
async def main():
    # --- تنظیمات ---
    BOT_TOKEN = Config.BOT_TOKEN
    CHAT_ID = Config.CHAT_ID
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
