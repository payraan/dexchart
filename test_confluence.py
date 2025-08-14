import asyncio
from analysis_engine import AnalysisEngine

async def test():
    engine = AnalysisEngine()
    
    # استفاده از SOL pool که حتماً فعاله
    pool_id = "solana_Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE"
    symbol = "SOL"
    
    print(f"🔄 Testing with {symbol}...")
    result = await engine.perform_full_analysis(pool_id, "hour", "1", symbol)
    
    if result:
        zones = result['technical_levels']['zones']
        print(f"✅ Analysis successful for {symbol}!")
        print(f"📊 Tier 1 Critical: {len(zones.get('tier1_critical', []))} zones")
        print(f"📊 Tier 2 Major: {len(zones.get('tier2_major', []))} zones")
        print(f"📊 Tier 3 Minor: {len(zones.get('tier3_minor', []))} zones")
        
        print("\n🔸 Tier 1 Details:")
        for i, zone in enumerate(zones.get('tier1_critical', []), 1):
            print(f"  Zone {i}:")
            print(f"    Score: {zone.get('final_score', 0):.1f}")
            print(f"    Price: ${zone.get('level_price', 0):.6f}")
            if zone.get('is_origin'):
                print(f"    Type: Origin Zone")
            elif zone.get('is_confluence'):
                fibs = zone.get('matched_fibs', [])
                print(f"    Type: Confluence")
                print(f"    Matched Fibs: {fibs}")
    else:
        print("❌ Analysis failed")

asyncio.run(test())
