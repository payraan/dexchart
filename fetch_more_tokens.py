import httpx
import asyncio
from database_manager import db_manager
from datetime import datetime

async def fetch_from_dexscreener():
    """دریافت توکن‌های ترند از DexScreener"""
    # تغییر URL به trending tokens
    url = "https://api.dexscreener.com/latest/dex/search/trending"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # بررسی ساختار داده
            if data and isinstance(data, list):
                tokens_added = 0
                
                for item in data[:30]:  # 30 توکن اول
                    if isinstance(item, dict):
                        address = item.get('tokenAddress')
                        symbol = item.get('tokenSymbol')
                        
                        if address and symbol:
                            query = '''INSERT OR IGNORE INTO watchlist_tokens
                                      (address, symbol, pool_id, first_seen, last_active, status)
                                      VALUES (?, ?, ?, ?, ?, 'active')'''
                            
                            now = datetime.now().isoformat()
                            pool_id = f"solana_{address}"
                            
                            db_manager.execute(query, (address, symbol, pool_id, now, now))
                            tokens_added += 1
                            print(f"Added: {symbol}")
                
                print(f"✅ Total added: {tokens_added} tokens")
            else:
                print("❌ Unexpected data format")
                print(f"Data type: {type(data)}")
                if data:
                    print(f"First item: {str(data)[:200]}")

asyncio.run(fetch_from_dexscreener())
