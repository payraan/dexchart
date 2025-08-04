import asyncio
import logging
from datetime import datetime
from token_cache import TokenCache
from strategy_engine import StrategyEngine
from telegram import Bot
from config import Config
from database_manager import db_manager

class BackgroundScanner:
    def __init__(self, bot_token, chat_id, scan_interval=120):
        self.token_cache = TokenCache()
        self.strategy_engine = StrategyEngine()
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        self.scan_interval = scan_interval
        self.running = False
        self.logger = logging.getLogger(__name__)
        
        # --- بخش جدید: متغیرهای مانیتورینگ ---
        self.last_scan_time = None
        self.scan_count = 0
        self.last_error = None
        # ------------------------------------

    async def send_signal_alert(self, signal):
        # این تابع بدون تغییر باقی می‌ماند
        try:
            analysis_result = signal.get('analysis_result')
            symbol = signal['symbol']
            token_address = signal['token_address']
            
            self.logger.info(f"🎨 Creating chart for {symbol}...")
            
            chart_image = await self.strategy_engine.analysis_engine.create_chart(
                analysis_result
            )
        
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

            placeholder = "%s" if db_manager.is_postgres else "?"
            query = f"SELECT last_message_id FROM watchlist_tokens WHERE address = {placeholder}"
            result = db_manager.fetchone(query, (token_address,))
            reply_to_message_id = result['last_message_id'] if result and result['last_message_id'] else None

            if chart_image:
                sent_message = await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=chart_image,
                    caption=message,
                    parse_mode='Markdown',
                    reply_to_message_id=reply_to_message_id
                )
                self.logger.info(f"📊 Chart + Alert for {symbol} sent.")
            else:
                sent_message = await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode='Markdown',
                    reply_to_message_id=reply_to_message_id
                )
                self.logger.info(f"📱 Text alert for {symbol} sent.")

            update_query = f"UPDATE watchlist_tokens SET last_message_id = {placeholder} WHERE address = {placeholder}"
            db_manager.execute(update_query, (sent_message.message_id, token_address))
            
        except Exception as e:
            self.logger.error(f"❌ Error sending Telegram alert for {symbol}: {e}")


    async def scan_tokens(self):
      """تمام توکن‌ها را برای یافتن سیگنال اسکن می‌کند."""
      # --- بخش جدید: به‌روزرسانی متغیرهای مانیتورینگ ---
      self.last_scan_time = datetime.now().isoformat()
      self.scan_count += 1
      self.logger.info(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Starting background scan #{self.scan_count}...")
      # ------------------------------------------------

      trending_tokens = self.token_cache.get_trending_tokens(limit=50)
      watchlist_tokens = self.token_cache.get_watchlist_tokens(limit=150)
      tokens = trending_tokens + watchlist_tokens
      
      seen_addresses = set()
      unique_tokens = [t for t in tokens if t['address'] not in seen_addresses and not seen_addresses.add(t['address'])]

      self.logger.info(f"📊 Scanning {len(unique_tokens)} unique tokens...")

      if not unique_tokens:
          self.logger.warning("No tokens found to scan.")
          return

      signals_found = 0
      for token in unique_tokens:
          try:
              df_test = await self.strategy_engine.analysis_engine.get_historical_data(token['pool_id'], "hour", "1", 50)
              is_new_token = df_test.empty or len(df_test) < 48

              if is_new_token:
                  timeframe, aggregate = "minute", "15"
              else:
                  timeframe, aggregate = "hour", "1"

              analysis_result = await self.strategy_engine.analysis_engine.perform_full_analysis(
                  token['pool_id'],
                  timeframe=timeframe,
                  aggregate=aggregate,
                  symbol=token['symbol']
              )

              if not analysis_result:
                  continue

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
                      self.logger.info(f"✅ Signal for {signal['symbol']} processed and sent.")
                  else:
                      self.logger.info(f"🔵 Cooldown active for {signal['symbol']}. Signal skipped.")

          except Exception as e:
              self.last_error = str(e)
              self.logger.error(f"❌ Error scanning {token.get('symbol', 'Unknown')}: {e}", exc_info=True)

      self.logger.info(f"📊 Scan #{self.scan_count} complete. {signals_found} new signals found.")


    async def start_scanning(self):
        """اسکن مداوم پس‌زمینه را آغاز می‌کند."""
        self.running = True
        self.logger.info(f"🚀 Background scanner started (Interval: {self.scan_interval}s).")

        try:
            initial_tokens = await self.token_cache.fetch_trending_tokens()
            if initial_tokens:
                self.logger.info(f"✅ Initial token list with {len(initial_tokens)} tokens fetched and saved.")
            else:
                self.logger.warning("Initial token list could not be fetched.")
        except Exception as e:
            self.logger.error(f"❌ Error fetching initial token list: {e}")

        while self.running:
            try:
                await self.scan_tokens()
                self.logger.info(f"⏳ Waiting {self.scan_interval} seconds for the next scan...")
                await asyncio.sleep(self.scan_interval)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                self.last_error = str(e)
                self.logger.critical(f"❌ CRITICAL SCANNER ERROR: {e}", exc_info=True)
                self.logger.info("⏳ Waiting 60 seconds due to critical error...")
                await asyncio.sleep(60)
        
        self.logger.info("\n🛑 Scanner stopped.")

# کد main بدون تغییر باقی می‌ماند
