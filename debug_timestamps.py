import asyncio
from telegram_bot import get_geckoterminal_ohlcv
from datetime import datetime

async def debug_timestamps():
    # همون pool_id که تست می‌کنی
    pool_id = "solana_71Jvq4Epe2FCJ7FSF7iLXdNk1Wy4Bhqd9jL6bEFELvg"
    
    print("Testing hour data...")
    ohlcv = await get_geckoterminal_ohlcv(pool_id, "hour", "1")
    
    if ohlcv:
        print(f"Total candles: {len(ohlcv)}")
        print("First 3 timestamps:")
        for i in range(3):
            timestamp = ohlcv[i][0]
            dt = datetime.fromtimestamp(timestamp)
            print(f"{i}: {timestamp} -> {dt}")
        
        print("\nLast 3 timestamps:")
        for i in range(-3, 0):
            timestamp = ohlcv[i][0]
            dt = datetime.fromtimestamp(timestamp)
            print(f"{i}: {timestamp} -> {dt}")

asyncio.run(debug_timestamps())
