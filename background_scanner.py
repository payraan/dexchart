import asyncio
import logging
from datetime import datetime
from token_cache import TokenCache
from strategy_engine import StrategyEngine
from telegram import Bot
from config import Config
from database_manager import db_manager
from holder_analyzer import HolderAnalyzer

class BackgroundScanner:
    def __init__(self, bot_token, chat_id, scan_interval=120):
        self.token_cache = TokenCache()
        self.strategy_engine = StrategyEngine()
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        self.scan_interval = scan_interval
        self.running = False
        self.logger = logging.getLogger(__name__)
        self.last_scan_time = None
        self.scan_count = 0
        self.holder_analyzer = HolderAnalyzer()
        self.last_error = None

    async def send_signal_alert(self, signal):
       """یک هشدار سیگنال را بر اساس نوع آن به تلگرام ارسال می‌کند."""
       try:
           signal_type = signal.get('signal_type', '')
           symbol = signal.get('symbol', 'N/A')
           token_address = signal.get('token_address')
           analysis_result = signal.get('analysis_result')
           current_price = signal.get('current_price', 0)

           # دریافت اطلاعات هولدر (قبل از ساخت پیام)
           holder_info_text = ""
           try:
               holder_data = await self.holder_analyzer.get_holder_stats(token_address)
               if holder_data:
                   holder_parts = []
                   
                   # تعداد هولدرها
                   if 'holder_count' in holder_data:
                       holder_parts.append(f"👥 {holder_data['holder_count']:,}")
                   
                   # تغییرات
                   if 'deltas' in holder_data:
                       h1 = holder_data['deltas'].get('1hour', 0)
                       if h1 != 0:
                           emoji = "📈" if h1 > 0 else "📉"
                           holder_parts.append(f"{emoji} 1h: {h1:+d}")
                   
                   # whale ها
                   if 'breakdowns' in holder_data:
                       whales = holder_data['breakdowns'].get('holders_over_100k_usd', 0)    
                       if whales > 0:
                           holder_parts.append(f"🐋 {whales}")
                   
                   if holder_parts:
                       holder_info_text = "\n**Holders:** " + " | ".join(holder_parts)
           except Exception as e:
               self.logger.error(f"Error getting holder data: {e}")

           # ساخت پیام بر اساس نوع سیگنال
           if signal_type.startswith('GEM_'):
               message = (
                   f"💎 *GEM HUNTER ALERT* 💎\n\n"
                   f"**Token:** *{symbol}*\n"
                   f"**Signal:** `{signal_type}`\n"                 
                   f"**Price:** `${current_price:.8f}`\n\n"
                   f"{holder_info_text}\n"
                   f"**Details:** `{signal.get('details', 'N/A')}`\n"
                   f"Time: `{signal.get('timestamp', '')}`"
               )
           elif signal_type == 'support_test':
               support_level = signal.get('support_level', 0)
               message = (
                   f"📈 *SUPPORT ZONE TEST*\n\n"
                   f"**Token:** *{symbol}*\n"
                   f"**Zone Score:** `{signal.get('zone_score', 0):.1f}/10`\n"
                   f"**Final Score:** `{signal.get('final_score', 0):.1f}/10`\n"
                   f"**Current Price:** `${current_price:.6f}`\n"
                   f"{holder_info_text}\n"
                   f"**Support Level:** `${support_level:.6f}`\n"
                   f"**Distance:** `{((current_price - support_level) / support_level * 100):+.1f}%`\n\n"
                   f"Time: `{signal.get('timestamp', '')}`"
               )
           elif 'breakout' in signal_type or 'resistance' in signal_type:
               broken_level = signal.get('level_broken', 0)
               message = (
                   f"🚀 *RESISTANCE BREAKOUT*\n\n"
                   f"**Token:** *{symbol}*\n"
                   f"**Zone Score:** `{signal.get('zone_score', 0):.1f}/10`\n"
                   f"**Final Score:** `{signal.get('final_score', 0):.1f}/10`\n"
                   f"**Current Price:** `${current_price:.6f}`\n"
                   f"{holder_info_text}\n"
                   f"**Broken Level:** `${broken_level:.6f}`\n"
                   f"**Breakout:** `{((current_price - broken_level) / broken_level * 100):+.1f}%`\n\n"
                   f"Time: `{signal.get('timestamp', '')}`"
               )
           else:
               # fallback برای سیگنال‌های جدید
               message = (
                   f"🔍 *ZONE SIGNAL*\n\n"
                   f"**Token:** *{symbol}*\n"
                   f"**Signal:** `{signal_type}`\n"
                   f"**Price:** `${current_price:.6f}`\n\n"
                   f"Time: `{signal.get('timestamp', '')}`"
               )

           # ساخت چارت
           chart_image = None
           if analysis_result:
               self.logger.info(f"🎨 Creating chart for {symbol}...")
               chart_image = await self.strategy_engine.analysis_engine.create_chart(analysis_result)

           # دریافت message_id قبلی برای reply
           placeholder = "%s" if db_manager.is_postgres else "?"
           query = f"SELECT last_message_id FROM watchlist_tokens WHERE address = {placeholder}"
           result = db_manager.fetchone(query, (token_address,))
           reply_to_message_id = result.get('last_message_id') if result and result.get('last_message_id') else None

           # ارسال پیام
           try:
               if chart_image:
                   try:
                       sent_message = await asyncio.wait_for(
                           self.bot.send_photo(
                               chat_id=self.chat_id, 
                               photo=chart_image, 
                               caption=message,
                               parse_mode='Markdown', 
                               reply_to_message_id=reply_to_message_id
                           ),
                           timeout=10  # حداکثر 10 ثانیه
                       )
                       self.logger.info(f"📊 Chart + Alert for {symbol} sent.")
                   except asyncio.TimeoutError:
                       # اگر چارت timeout شد، پیام متنی بفرست
                       sent_message = await asyncio.wait_for(
                           self.bot.send_message(
                               chat_id=self.chat_id, 
                               text=message, 
                               parse_mode='Markdown',
                               reply_to_message_id=reply_to_message_id
                           ),
                           timeout=5
                       )
                       self.logger.info(f"📱 Text alert for {symbol} sent (chart timed out).")
               else:
                   sent_message = await asyncio.wait_for(
                       self.bot.send_message(
                           chat_id=self.chat_id, 
                           text=message, 
                           parse_mode='Markdown',
                           reply_to_message_id=reply_to_message_id
                       ),
                       timeout=5
                   )
                   self.logger.info(f"📱 Text alert for {symbol} sent.")

               # آپدیت message_id در دیتابیس
               if sent_message:
                   update_query = f"UPDATE watchlist_tokens SET last_message_id = {placeholder} WHERE address = {placeholder}"
                   db_manager.execute(update_query, (sent_message.message_id, token_address))
                   
           except asyncio.TimeoutError:
               self.logger.error(f"⏱️ Telegram timeout for {symbol} - skipping")
           except Exception as e:
               self.logger.error(f"❌ Error sending alert for {symbol}: {e}")

       except Exception as e:
           self.logger.error(f"❌ Error sending Telegram alert for {signal.get('symbol', 'N/A')}: {e}", exc_info=True)

    async def scan_tokens(self):
       """اسکن هوشمند توکن‌ها با استفاده از روتر برای انتخاب استراتژی مناسب."""
       self.last_scan_time = datetime.now().isoformat()
       self.scan_count += 1
       self.logger.info(f"🔍 [SCAN #{self.scan_count}] Starting scan...")
           
       trending_tokens = self.token_cache.get_trending_tokens(limit=50)
       watchlist_tokens = self.token_cache.get_watchlist_tokens(limit=150)
       tokens = trending_tokens + watchlist_tokens
               
       seen_addresses = set()
       unique_tokens = [t for t in tokens if t['address'] not in seen_addresses and not seen_addresses.add(t['address'])]
                   
       self.logger.info(f"📊 Scanning {len(unique_tokens)} unique tokens...")
       signals_found = 0
                   
       for token in unique_tokens:
           signal = None
           try:
               timeframe_result = await self.strategy_engine.select_optimal_timeframe(token['pool_id'])
                   
               if timeframe_result[0]:
                   timeframe_data, cached_df = timeframe_result
                   timeframe, aggregate = timeframe_data
                   
                   # محاسبه عمر واقعی از روی timestamp ها
                   if cached_df is not None and not cached_df.empty and 'timestamp' in cached_df.columns:
                       first_ts = cached_df['timestamp'].iloc[0]
                       last_ts = cached_df['timestamp'].iloc[-1]
                       age_hours = (last_ts - first_ts) / 3600
                       age_days = age_hours / 24
                   else:
                       # fallback به تعداد رکوردها
                       age_hours = len(cached_df) if cached_df is not None else 0
                       age_days = age_hours / 24
                   
                   # تصمیم‌گیری بر اساس عمر واقعی
                   if age_days < 5:  # توکن‌های زیر 1 روز
                       self.logger.info(f"💎 [GEM HUNTER] Routing {token['symbol']} (Age: {age_days:.2f} days / {age_hours:.1f} hours)")
                       df_5min = await self.strategy_engine.analysis_engine.get_historical_data(
                           token['pool_id'], "minute", "5", limit=300
                       )
                       if df_5min is not None and not df_5min.empty and len(df_5min) >= 12:
                           signal = await self.strategy_engine.detect_gem_momentum_signal(df_5min, token)
                       else:
                           self.logger.info(f"⏳ {token['symbol']} is too new, waiting for more 5m data...")
                   else:
                       # توکن‌های بالای 1 روز - timeframe از select_optimal_timeframe میاد
                       self.logger.info(f"📈 [SMART] Routing {token['symbol']} (Age: {age_days:.1f} days) → {aggregate}{timeframe[0].upper()}")
                       analysis_result = await self.strategy_engine.analysis_engine.perform_full_analysis(
                           token['pool_id'], timeframe, aggregate, token['symbol']
                       )
                       if analysis_result:
                           signal = await self.strategy_engine.detect_breakout_signal(analysis_result, token['address'])
               
               if signal:
                   is_recent = await self.strategy_engine.has_recent_alert(signal)
                   if not is_recent:
                       signals_found += 1
                       await self.strategy_engine.save_alert(signal)
                       await self.send_signal_alert(signal)
                       self.logger.info(f"✅ Signal for {signal['symbol']} ({signal.get('signal_type')}) processed and sent.")
                   else:
                       self.logger.info(f"🔵 Cooldown active for {signal['symbol']}. Signal skipped.")

           except Exception as e:
               self.last_error = str(e)
               self.logger.error(f"❌ Error scanning {token.get('symbol', 'Unknown')}: {e}", exc_info=True)
   
           await asyncio.sleep(5.0)  # delay
       
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
