import asyncio
import httpx

async def test_api():
    pool_id = "solana_71Jvq4Epe2FCJ7FSF7iLXdNk1Wy4Bhqd9jL6bEFELvg"
    network, pool_address = pool_id.split('_')
    url = f"https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}/ohlcv/hour"
    
    params = {
        'aggregate': '1',
        'limit': '1000'
    }
    
    print(f"Testing URL: {url}")
    print(f"Params: {params}")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            ohlcv_list = data.get('data', {}).get('attributes', {}).get('ohlcv_list', [])
            print(f"Data points: {len(ohlcv_list)}")
            if ohlcv_list:
                print(f"First: {ohlcv_list[0]}")
                print(f"Last: {ohlcv_list[-1]}")
        else:
            print(f"Error: {response.text}")

asyncio.run(test_api())
