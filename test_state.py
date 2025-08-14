import asyncio
from strategy_engine import StrategyEngine
from analysis_engine import AnalysisEngine

async def test_state_management():
    strategy = StrategyEngine()
    analysis = AnalysisEngine()
    
    pool_id = "solana_Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE"
    token_address = "So11111111111111111111111111111111111111112"
    
    print("🔄 Test 1: First signal...")
    result = await analysis.perform_full_analysis(pool_id, "hour", "1", "SOL")
    signal1 = await strategy.detect_breakout_signal(result, token_address)
    
    if signal1:
        print(f"✅ Signal 1: {signal1['signal_type']}")
    
    print("\n🔄 Test 2: Same price again (should NOT signal)...")
    signal2 = await strategy.detect_breakout_signal(result, token_address)
    
    if signal2:
        print(f"❌ ERROR: Duplicate signal!")
    else:
        print(f"✅ Correctly blocked duplicate signal")
    
    # چک کردن state در دیتابیس
    print("\n📊 Checking saved states:")
    from database_manager import db_manager
    
    states = db_manager.fetchall(
        "SELECT * FROM zone_states WHERE token_address = ? ORDER BY zone_price",
        (token_address,)
    )
    
    for state in states:
        print(f"   Zone ${state['zone_price']:.2f}: {state['current_state']}")

asyncio.run(test_state_management())

