import asyncio
from strategy_engine import StrategyEngine
from analysis_engine import AnalysisEngine

async def test_signals():
    strategy = StrategyEngine()
    analysis = AnalysisEngine()
    
    tokens = [
        ("solana_Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE", "SOL", "So11111111111111111111111111111111111111112"),  # قدیمی
        ("solana_3vu9QTWWxEDNmoqRNEfb9Cvke2xBDJcJ1bdL8coYQSF1", "fatgirls", "test123")  # جدید
    ]
    
    for pool_id, symbol, address in tokens:
        print(f"\n🔍 Testing {symbol}:")
        
        # برای توکن جدید از GEM
        if "fatgirls" in symbol:
            df = await analysis.get_historical_data(pool_id, "minute", "15", limit=100)
            if df is not None and not df.empty:
                signal = await strategy.detect_gem_momentum_signal(df, {'pool_id': pool_id, 'symbol': symbol, 'address': address}, "minute", "15")
                if signal:
                    print(f"  → GEM Signal: {signal.get('signal_type')}")
        
        # برای همه از zone detection
        result = await analysis.perform_full_analysis(pool_id, "hour", "1", symbol)
        if result:
            signal = await strategy.detect_breakout_signal(result, address)
            if signal:
                print(f"  → Zone Signal: {signal.get('signal_type')}, Tier: {signal.get('zone_tier')}")
            else:
                print(f"  → No zone signal")

asyncio.run(test_signals())
