import asyncio
from analysis_engine import AnalysisEngine

async def test_slop():
    engine = AnalysisEngine()
    pool_id = "solana_DwTSZ1Jk2H1d8Dshgyg1xBfyNhoTmbwczjM4w2FfHdA2"
    
    # دریافت آخرین داده
    df = await engine.get_historical_data(pool_id, "minute", "15", 50)
    if not df.empty:
        latest = df.iloc[-1]
        print(f"قیمت فعلی از API: ${latest['close']:.6f}")
        print(f"حجم فعلی: {latest['volume']:.2f}")
        print(f"آخرین بروزرسانی: {latest['timestamp']}")
    else:
        print("داده‌ای دریافت نشد")

asyncio.run(test_slop())
