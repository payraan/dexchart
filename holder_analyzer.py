import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import logging
from config import TradingConfig

class HolderAnalyzer:
    def __init__(self, api_key: str = TradingConfig.HOLDER_API_KEY):
        """
        ساختار اصلی کلاس با مدیریت صحیح کلید API.
        """
        self.api_key = api_key
        self.base_url = "https://api.holderscan.com/v0"
        self.headers = {"x-api-key": self.api_key}
        self.logger = logging.getLogger(__name__)

        # این متغیر به صورت استاندارد، فعال بودن این ماژول را کنترل می‌کند
        self.is_enabled = bool(self.api_key)

        if not self.is_enabled:
            self.logger.warning("⚠️ HolderScan API is DISABLED - No API key found in config.")

    async def _make_request(self, url: str) -> Optional[Dict]:
        """یک متد داخلی برای ارسال درخواست‌ها جهت جلوگیری از تکرار کد و مدیریت خطا"""
        if not self.is_enabled:
            return None

        try:
            # استفاده از کانکتور برای حل مشکلات احتمالی SSL
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, headers=self.headers, timeout=7) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 429:
                        self.logger.warning(f"HolderScan API rate limited for url: {url}")
                    # خطای 404 طبیعی است (توکن پیدا نشده)، پس لاگ نمی‌کنیم
                    elif resp.status != 404:
                        self.logger.error(f"HolderScan API returned status {resp.status} for {url}")
        except asyncio.TimeoutError:
            self.logger.warning(f"HolderScan API request timed out for url: {url}")
        except Exception as e:
            self.logger.error(f"Error making HolderScan request to {url}: {e}")

        return None

    async def get_holder_stats(self, token_address: str) -> Optional[Dict]:
        """
        دریافت آمار کامل هولدرها برای یک توکن Solana.
        این تابع بازنویسی شده تا از متد کمکی _make_request استفاده کند.
        """
        if not self.is_enabled:
            return None

        self.logger.info(f"🔎 Fetching holder data for {token_address}")
        holder_data = {}
        chain_id = "sol"

        # 1. دریافت تعداد هولدرها
        holders_url = f"{self.base_url}/{chain_id}/tokens/{token_address}/holders?limit=1"
        holders_info = await self._make_request(holders_url)
        if holders_info and 'holder_count' in holders_info:
            holder_data['holder_count'] = holders_info.get('holder_count', 0)
            self.logger.info(f"✅ Holders: {holder_data['holder_count']}")

            # 2. دریافت تغییرات هولدرها (فقط اگر holder_count موجود باشه)
            deltas_info = await self.get_holder_deltas(token_address)
            if deltas_info:
                holder_data['deltas'] = deltas_info
                self.logger.info(f"✅ Deltas: 1h={deltas_info.get('1hour', 0)}")

            # 3. دریافت توزیع هولدرها (فقط اگر holder_count موجود باشه)
            breakdown_url = f"{self.base_url}/{chain_id}/tokens/{token_address}/holders/breakdowns"
            breakdown_info = await self._make_request(breakdown_url)
            if breakdown_info:
                holder_data['breakdowns'] = breakdown_info
                whales = breakdown_info.get('holders_over_100k_usd', 0)
                self.logger.info(f"✅ Whales: {whales}")

        return holder_data if holder_data else None

    async def get_holder_deltas(self, token_address: str) -> Optional[Dict]:
        """فقط اطلاعات تغییرات هولدرها را دریافت می‌کند."""
        if not self.is_enabled:
            return None
        chain_id = "sol"
        deltas_url = f"{self.base_url}/{chain_id}/tokens/{token_address}/holders/deltas"
        return await self._make_request(deltas_url)

    def enrich_signal_with_holders(self, signal: Dict, holder_data: Dict) -> Dict:
        """
        اضافه کردن اطلاعات هولدر به سیگنال موجود (این تابع بدون تغییر باقی مانده).
        """
        if not holder_data:
            return signal

        holder_info = []

        # تعداد کل هولدرها
        if 'holder_count' in holder_data:
            holder_info.append(f"👥 {holder_data['holder_count']:,} holders")

        # تغییرات هولدرها
        if 'deltas' in holder_data:
            deltas = holder_data['deltas']
            hour_change = deltas.get('1hour', 0)
            day_change = deltas.get('1day', 0)

            if hour_change != 0:
                emoji = "📈" if hour_change > 0 else "📉"
                holder_info.append(f"{emoji} 1h: {hour_change:+d}")

            if day_change != 0:
                emoji = "💚" if day_change > 0 else "🔴"
                holder_info.append(f"{emoji} 24h: {day_change:+d}")

            # سیگنال‌های خاص
            if hour_change > 100:
                holder_info.append("🚀 MASS ENTRY!")
            elif hour_change < -50:
                holder_info.append("⚠️ MASS EXIT!")

        # توزیع هولدرها
        if 'breakdowns' in holder_data:
            breakdowns = holder_data['breakdowns']
            whales = breakdowns.get('holders_over_100k_usd', 0)

            if whales > 0:
                holder_info.append(f"🐋 {whales} whales")

            # محاسبه نسبت whale به کل
            total = breakdowns.get('total_holders', 1)
            if total > 0 and 'categories' in breakdowns:
                whale_count = breakdowns['categories'].get('whale', 0)
                whale_ratio = (whale_count / total) * 100
                if whale_ratio > 5:
                    holder_info.append(f"💎 Whale ratio: {whale_ratio:.1f}%")

        # اضافه کردن به سیگنال
        if holder_info:
            signal['holder_info'] = " | ".join(holder_info)

        return signal
