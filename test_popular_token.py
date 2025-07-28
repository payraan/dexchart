import asyncio
import httpx

async def test_popular_tokens():
    # چندتا token محبوب solana
    test_addresses = [
        "So11111111111111111111111111111111111111112",  # Wrapped SOL
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", # USDC
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"  # USDT
    ]
    
    for address in test_addresses:
        print(f"\nTesting: {address}")
        
        # اول باید pool_id پیدا کنیم
        search_url = f"https://api.geckoterminal.com/api/v2/search/pools?query={address}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(search_url)
            if response.status_code == 200:
                data = response.json()
                pools = data.get('data', [])
                if pools:
                    pool_id = pools[0]['id']
                    print(f"✅ Found pool: {pool_id}")
                    break
                else:
                    print("❌ No pools found")
            else:
                print(f"❌ Search failed: {response.status_code}")

asyncio.run(test_popular_tokens())
