import asyncio
from analysis_engine import AnalysisEngine

async def debug_zones():
    engine = AnalysisEngine()
    
    # تست با یک توکن
    pool_id = "solana_3vu9QTWWxEDNmoqRNEfb9Cvke2xBDJcJ1bdL8coYQSF1"  # fatgirls
    symbol = "fatgirls"
    
    print("🔄 Analyzing for zones...")
    result = await engine.perform_full_analysis(pool_id, "minute", "15", symbol)
    
    if result:
        zones = result['technical_levels']['zones']
        
        print("\n📊 ZONES FOUND:")
        print(f"Tier 1 Critical: {len(zones.get('tier1_critical', []))}")
        print(f"Tier 2 Major: {len(zones.get('tier2_major', []))}")
        print(f"Supply: {len(zones.get('supply', []))}")
        print(f"Demand: {len(zones.get('demand', []))}")
        
        # جزئیات Tier 1
        for t1 in zones.get('tier1_critical', []):
            print(f"\n🔸 Tier 1 Zone:")
            print(f"   Price: ${t1.get('level_price', 0):.8f}")
            print(f"   Score: {t1.get('final_score', 0):.1f}")
            print(f"   Is Origin: {t1.get('is_origin', False)}")
            print(f"   Is Confluence: {t1.get('is_confluence', False)}")

asyncio.run(debug_zones())
