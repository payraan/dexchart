import asyncio
from token_health import TokenHealthChecker
import pandas as pd

async def test():
    checker = TokenHealthChecker()
    
    # شبیه‌سازی یک توکن rugged
    fake_df = pd.DataFrame({
        'timestamp': [1000, 2000, 3000],
        'high': [1.0, 0.5, 0.1],
        'low': [0.9, 0.4, 0.05],
        'close': [0.95, 0.45, 0.08],
        'volume': [1000, 500, 100]
    })
    
    fake_token = {
        'symbol': 'TEST',
        'address': 'test123',
        'volume_24h': 5000  # حجم پایین
    }
    
    result = await checker.check_token_health(fake_token, fake_df)
    print(f"Test Result: {result}")

asyncio.run(test())
