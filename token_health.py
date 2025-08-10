# token_health.py
import logging
from datetime import datetime, timedelta
from database_manager import db_manager
from holder_analyzer import HolderAnalyzer # از کلاس اصلاح شده استفاده می‌کند

logger = logging.getLogger(__name__)

class TokenHealthChecker:
    def __init__(self):
        # آستانه‌های جدید طبق نقشه راه
        self.MIN_VOLUME_NEW = 100_000
        self.MIN_VOLUME_ESTABLISHED = 300_000
        self.MAX_ATH_DROP = 0.85
        self.HOLDER_DROP_THRESHOLD_1H = -15  # جریمه برای خروج بیش از ۱۵ هولدر در ساعت
        self.HOLDER_DROP_THRESHOLD_24H = -75 # جریمه برای خروج بیش از ۷۵ هولدر در روز

        # اتصال به هولدر آنالایزر اصلاح‌شده
        self.holder_analyzer = HolderAnalyzer()

    def get_token_age_hours(self, df):
        """محاسبه عمر توکن بر اساس داده‌های قیمتی (به ساعت)"""
        if df is not None and not df.empty and 'timestamp' in df.columns:
            first_ts = df['timestamp'].iloc[0]
            last_ts = df['timestamp'].iloc[-1]
            return (last_ts - first_ts) / 3600
        return 0

    async def check_token_health(self, token_data, price_history_df):
        """بررسی جامع سلامت توکن و محاسبه امتیاز نهایی"""
        health_score = 100.0
        issues = []
        symbol = token_data.get('symbol', 'N/A')

        # --- 1. بررسی افت از ATH ---
        if price_history_df is not None and not price_history_df.empty:
            ath = price_history_df['high'].max()
            current = price_history_df['close'].iloc[-1]

            if ath > 0:
                drop_ratio = (ath - current) / ath
                if drop_ratio > self.MAX_ATH_DROP:
                    health_score -= 70  # جریمه سنگین برای افت شدید
                    issues.append(f"ATH drop {drop_ratio:.1%}")

        # --- 2. بررسی حجم داینامیک ---
        age_hours = self.get_token_age_hours(price_history_df)
        volume = token_data.get('volume_24h', 0)

        min_volume_required = self.MIN_VOLUME_NEW if age_hours < 48 else self.MIN_VOLUME_ESTABLISHED

        if volume < min_volume_required:
            health_score -= 30  # جریمه برای حجم پایین
            issues.append(f"Low volume ${volume:,.0f} (needs >${min_volume_required:,.0f})")

        # --- 3. بررسی روند هولدرها (با استفاده از is_enabled) ---
        # *** این بخش اصلاح شده است ***
        if self.holder_analyzer.is_enabled:
            holder_deltas = await self.holder_analyzer.get_holder_deltas(token_data['address'])
            if holder_deltas:
                h1_delta = holder_deltas.get('1hour', 0)
                h24_delta = holder_deltas.get('1day', 0)

                # بررسی می‌کنیم که مقدار None نباشد
                if h1_delta is not None and h1_delta < self.HOLDER_DROP_THRESHOLD_1H:
                    health_score -= 25 # جریمه برای خروج ساعتی
                    issues.append(f"1h holder drop: {h1_delta}")
                if h24_delta is not None and h24_delta < self.HOLDER_DROP_THRESHOLD_24H:
                    health_score -= 40 # جریمه سنگین‌تر برای خروج روزانه
                    issues.append(f"24h holder drop: {h24_delta}")

        # --- 4. تعیین وضعیت نهایی ---
        if health_score < 20:
            status = 'rugged'
        elif health_score < 50:
            status = 'warning'
        else:
            status = 'active'

        # نمایش یک لاگ جامع و مفید
        issues_str = ", ".join(issues) if issues else "No issues"
        logger.info(f"🏥 {symbol}: Health={health_score:.0f}, Status={status} ({issues_str})")

        return {
            'health_score': health_score,
            'status': status,
            'issues': issues
        }
