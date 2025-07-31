from token_cache import TokenCache

cache = TokenCache()
tokens = cache.get_trending_tokens(limit=10)
for token in tokens:
    if token["symbol"] == "SLOP":
        print(f"SLOP Pool ID: {token['pool_id']}")
        print(f"Address: {token['address']}")
