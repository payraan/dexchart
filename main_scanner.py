import asyncio
from token_cache import TokenCache
from strategy_engine import StrategyEngine

class MainScanner:
    def __init__(self):
        """اسکنر اصلی و اجزای آن را مقداردهی اولیه می‌کند."""
        self.token_cache = TokenCache()
        self.strategy_engine = StrategyEngine()

    async def scan_all_tokens(self):
        """تمام توکن‌های ترند را برای یافتن سیگنال‌های معاملاتی اسکن می‌کند."""
        print("🔍 اسکن توکن‌ها آغاز شد...")

        # دریافت توکن‌های ترند از پایگاه داده
        tokens = self.token_cache.get_trending_tokens(limit=10)

        if not tokens:
            print("❌ هیچ توکنی برای اسکن در پایگاه داده یافت نشد.")
            return

        print(f"📊 در حال اسکن {len(tokens)} توکن برای سیگنال شکست (Breakout)...")
        print("-" * 40)

        signals_found = 0
        for token in tokens:
            try:
                # در حال حاضر فقط سیگنال شکست را شناسایی می‌کنیم
                signal = await self.strategy_engine.detect_breakout_signal(
                    token['address'],
                    token['pool_id'],
                    token['symbol']
                )

                if signal:
                    signals_found += 1
                    await self.strategy_engine.save_alert(signal)
                    # قالب‌بندی زیبای خروجی برای یک سیگنال واضح
                    print(f"🚀 هشدار شکست برای {signal['symbol']}!")
                    print(f"  - مقاومت شکسته شده: ${signal['resistance_level']:.6f}")
                    print(f"  - قیمت فعلی:        ${signal['current_price']:.6f}")
                    print(f"  - جهش حجم:          {signal['volume_ratio']:.1f}x حجم عادی")
                    print(f"  - زمان شناسایی:        {signal['timestamp']}")
                    print("-" * 40)

            except Exception as e:
                print(f"❌ خطایی هنگام تحلیل {token.get('symbol', 'Unknown')} رخ داد: {e}")

        print(f"✅ اسکن کامل شد. {signals_found} سیگنال بالقوه یافت شد.")

if __name__ == "__main__":
    print("--- اجرای اسکنر اصلی ---")
    scanner = MainScanner()
    # استفاده از asyncio.run() برای اجرای تابع async
    asyncio.run(scanner.scan_all_tokens())
