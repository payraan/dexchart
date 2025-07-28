import asyncio
from telegram_bot import find_geckoterminal_pool, get_geckoterminal_ohlcv
import pandas as pd

async def debug_ema():
    # Use USELESS token from trending
    token_address = "Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk"
    
    print("Finding pool...")
    pool_id, symbol = await find_geckoterminal_pool(token_address)
    print(f"Pool ID: {pool_id}")
    print(f"Symbol: {symbol}")
    
    if pool_id:
        print("Getting OHLCV data...")
        ohlcv = await get_geckoterminal_ohlcv(pool_id, "minute", "5")
        
        if ohlcv:
            print(f"Number of candles: {len(ohlcv)}")
            print(f"First candle: {ohlcv[0]}")
            print(f"Last candle: {ohlcv[-1]}")
            
            # Check timestamps order
            timestamps = [candle[0] for candle in ohlcv]
            is_ascending = all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))
            print(f"Timestamps ascending: {is_ascending}")
        else:
            print("No OHLCV data received")
    else:
        print("Pool not found")

asyncio.run(debug_ema())
