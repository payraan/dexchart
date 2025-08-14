import asyncio
from analysis_engine import AnalysisEngine

async def test_new_token():
    engine = AnalysisEngine()
    
    # توکن جدید
    pool_id = "solana_HJtdALk2oebbBJibixu6aFCoKUjQFUZjKDFvjoYZPxUa"
    symbol = "NEW_TOKEN"
    
    print(f"🆕 Testing new token...")
    print(f"📋 Contract: 7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump")
    print(f"🏊 Pool: {pool_id}\n")
    
    # تست با تایم‌فریم کوتاه برای توکن جدید
    result = await engine.perform_full_analysis(pool_id, "minute", "5", symbol)
    
    if result:
        zones = result['technical_levels']['zones']
        print(f"✅ Analysis successful!")
        print(f"📊 Tier 1 Critical: {len(zones.get('tier1_critical', []))} zones")
        print(f"📊 Tier 2 Major: {len(zones.get('tier2_major', []))} zones")
        
        # بررسی Origin Zone
        origin = zones.get('origin')
        if origin:
            print(f"\n🟠 ORIGIN ZONE DETECTED!")
            print(f"   Bottom: ${origin.get('zone_bottom', 0):.8f}")
            print(f"   Top: ${origin.get('zone_top', 0):.8f}")
            print(f"   Pump: {origin.get('pump_percent', 0):.1%}")
        
        print("\n🔸 All Tier 1 Zones:")
        for i, zone in enumerate(zones.get('tier1_critical', []), 1):
            print(f"  Zone {i}:")
            print(f"    Score: {zone.get('final_score', 0):.1f}")
            if zone.get('is_origin'):
                print(f"    Type: ⭐ ORIGIN ZONE")
            elif zone.get('is_confluence'):
                print(f"    Type: Confluence (Fibs: {zone.get('matched_fibs', [])})")
            else:
                print(f"    Type: Major Zone")
        
        # ساخت چارت
        print("\n📊 Creating chart...")
        chart = await engine.create_chart(result)
        if chart:
            with open('new_token_chart.png', 'wb') as f:
                f.write(chart.getvalue())
            print("✅ Chart saved as new_token_chart.png")
            print("🖼️ Open with: open new_token_chart.png")
    else:
        print("❌ Analysis failed - Token might be too new or inactive")

asyncio.run(test_new_token())
