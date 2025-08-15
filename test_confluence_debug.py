import asyncio
from analysis_engine import AnalysisEngine
from zone_config import CONFLUENCE_THRESHOLD, FIBONACCI_WEIGHTS

async def debug_confluence():
    engine = AnalysisEngine()
    
    pool_id = "solana_3vu9QTWWxEDNmoqRNEfb9Cvke2xBDJcJ1bdL8coYQSF1"
    result = await engine.perform_full_analysis(pool_id, "minute", "15", "fatgirls")
    
    if result:
        zones = result['technical_levels']['zones']
        fib_data = result['technical_levels'].get('fibonacci')
        
        print(f"🔍 Confluence Threshold: {CONFLUENCE_THRESHOLD*100:.1f}%\n")
        
        # نمایش Supply/Demand zones
        print("📊 Supply Zones:")
        for s in zones.get('supply', []):
            print(f"  ${s.get('level_price', 0):.8f} (Score: {s.get('score', 0):.1f})")
            
        print("\n📊 Demand Zones:")  
        for d in zones.get('demand', []):
            print(f"  ${d.get('level_price', 0):.8f} (Score: {d.get('score', 0):.1f})")
        
        # نمایش Fibonacci
        if fib_data and fib_data.get('levels'):
            print("\n📐 Fibonacci Levels:")
            for level, price in fib_data['levels'].items():
                if level in [0.382, 0.5, 0.618]:
                    print(f"  Fib {level}: ${price:.8f}")
        
        # محاسبه دستی فاصله‌ها
        print("\n🔄 Checking distances:")
        all_zones = zones.get('supply', []) + zones.get('demand', [])
        for zone in all_zones:
            zone_price = zone.get('level_price', 0)
            print(f"\nZone ${zone_price:.8f}:")
            if fib_data and fib_data.get('levels'):
                for fib_level, fib_price in fib_data['levels'].items():
                    if fib_level in FIBONACCI_WEIGHTS:
                        distance = abs(zone_price - fib_price) / zone_price if zone_price > 0 else 1
                        if distance < 0.1:  # فقط نزدیک‌ها رو نشون بده
                            print(f"  → Fib {fib_level}: {distance*100:.2f}% {'✅' if distance < CONFLUENCE_THRESHOLD else '❌'}")

asyncio.run(debug_confluence())
