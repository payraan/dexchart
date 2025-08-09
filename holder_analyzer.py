import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import logging

class HolderAnalyzer:
    def __init__(self, api_key: str = "14e3c68c1e547b0d52da17c9e34cf8c95e415a0d5187af12eda8e0218810269e"):
        self.api_key = api_key
        self.base_url = "https://api.holderscan.com/v0"
        self.headers = {"x-api-key": api_key}  # توجه: x-api-key نه Authorization
        self.logger = logging.getLogger(__name__)
        
    async def get_holder_stats(self, token_address: str) -> Optional[Dict]:
        """دریافت آمار کامل هولدرها برای یک توکن Solana"""
        self.logger.info(f"🔎 Fetching holder data for {token_address}")
        
        chain_id = "sol"  # برای Solana
        holder_data = {}
        
        try:
            async with aiohttp.ClientSession() as session:
                # 1. دریافت تعداد هولدرها
                holders_url = f"{self.base_url}/{chain_id}/tokens/{token_address}/holders?limit=1"
                self.logger.info(f"Calling: {holders_url}")
                
                async with session.get(holders_url, headers=self.headers, timeout=10) as resp:
                    self.logger.info(f"Status: {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        holder_data['holder_count'] = data.get('holder_count', 0)
                        self.logger.info(f"✅ Holders: {holder_data['holder_count']}")
                    else:
                        error = await resp.text()
                        self.logger.error(f"API Error: {error}")
                
                # 2. دریافت تغییرات هولدرها
                deltas_url = f"{self.base_url}/{chain_id}/tokens/{token_address}/holders/deltas"
                async with session.get(deltas_url, headers=self.headers, timeout=10) as resp:
                    if resp.status == 200:
                        holder_data['deltas'] = await resp.json()
                        self.logger.info(f"✅ Deltas: 1h={holder_data['deltas'].get('1hour', 0)}")
                
                # 3. دریافت توزیع هولدرها
                breakdown_url = f"{self.base_url}/{chain_id}/tokens/{token_address}/holders/breakdowns"
                async with session.get(breakdown_url, headers=self.headers, timeout=10) as resp:
                    if resp.status == 200:
                        holder_data['breakdowns'] = await resp.json()
                        whales = holder_data['breakdowns'].get('holders_over_100k_usd', 0)
                        self.logger.info(f"✅ Whales: {whales}")
                
                return holder_data if holder_data else None
                
        except Exception as e:
            self.logger.error(f"❌ Error in get_holder_stats: {e}", exc_info=True)
            return None
    
    def enrich_signal_with_holders(self, signal: Dict, holder_data: Dict) -> Dict:
        """اضافه کردن اطلاعات هولدر به سیگنال موجود"""
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
