import asyncio
import httpx

async def test_correct_address():
    pool_address = "71Jvq4Epe2FCJ7JFSF7jLXdNk1Wy4Bhqd9iL6bEFELvg"
    url = f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool_address}/ohlcv/hour"
    
    params = {'aggregate': '1', 'limit': '100'}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            ohlcv_list = data.get('data', {}).get('attributes', {}).get('ohlcv_list', [])
            print(f"✅ Success! Got {len(ohlcv_list)} data points")
        else:
            print(f"❌ Error: {response.text}")

asyncio.run(test_correct_address())
