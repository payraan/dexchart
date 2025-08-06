import httpx
import asyncio

async def check_api():
    url = 'https://api.geckoterminal.com/api/v2/networks/solana/trending_pools'
    params = {'include': 'base_token', 'limit': '50'}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        data = response.json()
        pools = data.get('data', [])
        print(f'🔍 API returned: {len(pools)} pools')
        
        # نمایش 5 توکن اول
        for i, pool in enumerate(pools[:5]):
            attrs = pool.get('attributes', {})
            vol = attrs.get('volume_usd', {}).get('h24', 0)
            name = attrs.get('name', 'Unknown')
            # تبدیل به float اگر string باشه
            if isinstance(vol, str):
                vol = float(vol) if vol else 0
            print(f'{i+1}. {name}: Volume ${vol:,.0f}')

asyncio.run(check_api())
