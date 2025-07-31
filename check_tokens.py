from token_cache import TokenCache

cache = TokenCache()
tokens = cache.get_trending_tokens(limit=10)
print('🔍 توکن‌های در حال بررسی:')
for i, token in enumerate(tokens, 1):
    print(f'{i}. {token["symbol"]} - ${token["price_usd"]:.6f}')
    print(f'   Address: {token["address"]}')
    print()
