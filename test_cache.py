import asyncio
from token_cache import TokenCache

async def test():
    cache = TokenCache()
    tokens = await cache.fetch_trending_tokens()
    print(f'Fetched {len(tokens)} tokens')
    
    # Show cached tokens
    cached = cache.get_trending_tokens(5)
    for token in cached:
        print(f'{token["symbol"]}: ${token["price_usd"]:.6f}')

asyncio.run(test())
