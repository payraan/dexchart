import asyncio
from analysis_engine import AnalysisEngine
from strategy_engine import StrategyEngine

async def test_signals():
    analysis = AnalysisEngine()
    strategy = StrategyEngine()
    
    # تست با SOL
    pool_id = "solana_Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE"
    symbol = "SOL"
    token_address = "So11111111111111111111111111111111111111112"
    
    print("🔄 Analyzing SOL...")
    result = await analysis.perform_full_analysis(pool_id, "hour", "1", symbol)
    
    if result:
        print(f"✅ Analysis complete")
        print(f"💰 Current Price: ${result['raw_data']['current_price']:.2f}")
        
        # تست سیگنال
        signal = await strategy.detect_breakout_signal(result, token_address)
        
        if signal:
            print(f"\n🚨 SIGNAL DETECTED!")
            print(f"   Type: {signal['signal_type']}")
            print(f"   Zone Tier: {signal.get('zone_tier')}")
            print(f"   Zone Price: ${signal.get('zone_price', 0):.2f}")
            print(f"   Distance: {signal.get('distance_percent', 0):.1f}%")
        else:
            print("\n📊 No signal at current price")
            
        # نمایش zones
        zones = result['technical_levels']['zones']
        print(f"\n📍 Active Zones:")
        for t1 in zones.get('tier1_critical', []):
            price = t1.get('level_price', 0)
            print(f"   Tier 1: ${price:.2f} (Score: {t1.get('final_score', 0):.1f})")

asyncio.run(test_signals())
