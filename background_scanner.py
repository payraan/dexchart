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
        self.last_scan_time = None
        self.scan_count = 0
        self.last_error = None

    async def send_signal_alert(self, signal):
        """یک هشدار سیگنال را بر اساس نوع آن به تلگرام ارسال می‌کند."""
        try:
            signal_type = signal.get('signal_type', '')
            symbol = signal.get('symbol', 'N/A')
            token_address = signal.get('token_address')
            analysis_result = signal.get('analysis_result')

            if signal_type.startswith('GEM_'):
                message = (
                    f"💎 *GEM HUNTER ALERT* 💎\n\n"
                    f"**Token:** *{symbol}*\n"
                    f"**Signal:** `{signal_type}`\n"
                    f"**Price:** `${signal.get('current_price', 0):.8f}`\n\n"
                    f"**Details:** `{signal.get('details', 'N/A')}`\n"
                    f"Time: `{signal.get('timestamp', '')}`"
                )
            else:
                message = (
                    f"🚀 *MAJOR ZONE BREAKOUT*\n\n"
                    f"**Token:** *{symbol}*\n"
                    f"**Signal:** `{signal_type}`\n"
                    f"**Zone Score:** `{signal.get('zone_score', 0):.1f}/10`\n"
                    f"**Final Score:** `{signal.get('final_score', 0):.1f}/10`\n"
                    f"**Price:** `${signal.get('current_price', 0):.6f}`\n"
                    f"**Level:** `${signal.get('level_broken', signal.get('support_level', 'N/A')):.6f}`\n\n"
                    f"Time: `{signal.get('timestamp', '')}`"
                )

            chart_image = None
            if analysis_result:
                self.logger.info(f"🎨 Creating chart for {symbol}...")
                chart_image = await self.strategy_engine.analysis_engine.create_chart(analysis_result)
            
            placeholder = "%s" if db_manager.is_postgres else "?"
            query = f"SELECT last_message_id FROM watchlist_tokens WHERE address = {placeholder}"
            result = db_manager.fetchone(query, (token_address,))
            reply_to_message_id = result.get('last_message_id') if result and result.get('last_message_id') else None

            if chart_image:
                sent_message = await self.bot.send_photo(
                    chat_id=self.chat_id, photo=chart_image, caption=message,
                    parse_mode='Markdown', reply_to_message_id=reply_to_message_id
                )
                self.logger.info(f"📊 Chart + Alert for {symbol} sent.")
            else:
                sent_message = await self.bot.send_message(
                    chat_id=self.chat_id, text=message, parse_mode='Markdown',
                    reply_to_message_id=reply_to_message_id
                )
                self.logger.info(f"📱 Text alert for {symbol} sent.")

            update_query = f"UPDATE watchlist_tokens SET last_message_id = {placeholder} WHERE address = {placeholder}"
            db_manager.execute(update_query, (sent_message.message_id, token_address))
            
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
                df_hourly = await self.strategy_engine.analysis_engine.get_historical_data(
                    token['pool_id'], "hour", "1", limit=100
                )
                hours_since_launch = len(df_hourly) if df_hourly is not None and not df_hourly.empty else 0

                if 0 < hours_since_launch < 24:
                    self.logger.info(f"💎 [GEM HUNTER] Routing {token['symbol']} (Age: {hours_since_launch}h)")
                    df_5min = await self.strategy_engine.analysis_engine.get_historical_data(
                        token['pool_id'], "minute", "5", limit=300
                    )
                    if df_5min is not None and not df_5min.empty and len(df_5min) >= 12:
                        signal = await self.strategy_engine.detect_gem_momentum_signal(df_5min, token)
                    else:
                        self.logger.info(f"⏳ {token['symbol']} is too new, waiting for more 5m data...")
                
                elif hours_since_launch >= 24:
                    # استفاده از Smart Timeframe Router
                    optimal_timeframe = await self.strategy_engine.select_optimal_timeframe(token['pool_id'])
    
                    if optimal_timeframe:
                        timeframe, aggregate = optimal_timeframe
                        self.logger.info(f"📈 [SMART] Routing {token['symbol']} (Age: {hours_since_launch}h) → {aggregate}{timeframe[0].upper()}")
        
                        analysis_result = await self.strategy_engine.analysis_engine.perform_full_analysis(
                            token['pool_id'], timeframe, aggregate, token['symbol']
                        )
                    else:
                        analysis_result = None

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

            await asyncio.sleep(2.5)  # 2.5 second delay
        
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
