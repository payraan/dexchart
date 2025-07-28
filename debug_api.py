import asyncio
import httpx

async def debug_api():
    url = "https://api.geckoterminal.com/api/v2/networks/solana/trending_pools"
    params = {
        'include': 'base_token,quote_token',
        'limit': '20'
    }

    print(f"Requesting: {url}")
    print(f"Params: {params}")

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Data keys: {data.keys()}")

            pools = data.get('data', [])
            print(f"Number of pools: {len(pools)}")

            if pools:
                first_pool = pools[0]
                print(f"First pool keys: {first_pool.keys()}")
                
                attributes = first_pool.get('attributes', {})
                print(f"First pool attributes: {attributes.keys()}")
                
                # Check specific fields we need
                print(f"\nChecking required fields:")
                print(f"base_token_address: {attributes.get('base_token_address', 'NOT FOUND')}")
                print(f"base_token_symbol: {attributes.get('base_token_symbol', 'NOT FOUND')}")
                print(f"base_token_price_usd: {attributes.get('base_token_price_usd')}")
                print(f"name: {attributes.get('name')}")
                
                # Check volume structure
                volume_usd = attributes.get('volume_usd', {})
                print(f"volume_usd type: {type(volume_usd)}")
                print(f"volume_usd: {volume_usd}")
        else:
            print(f"Error: {response.text}")

asyncio.run(debug_api())
