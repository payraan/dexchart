import asyncio
from analysis_engine import AnalysisEngine
from zone_config import CONFLUENCE_THRESHOLD, FIBONACCI_WEIGHTS

async def debug_confluence():
    engine = AnalysisEngine()
    
    pool_id = "solana_HJtdALk2oebbBJibixu6aFCoKUjQFUZjKDFvjoYZPxUa"
    result = await engine.perform_full_analysis(pool_id, "minute", "5", "TOKEN")
    
    if result:
        zones = result['technical_levels']['zones']
        fib_data = result['technical_levels'].get('fibonacci')
        
        # بررسی دستی confluence
        demand_zones = zones.get('demand', [])
        
        print("🔍 Checking Confluence manually:")
        print(f"Threshold: {CONFLUENCE_THRESHOLD*100:.1f}%\n")
        
        for i, zone in enumerate(demand_zones, 1):
            zone_price = zone.get('level_price', 0)
            print(f"Zone {i}: ${zone_price:.8f} (Base Score: {zone.get('score', 0):.1f})")
            
            if fib_data and fib_data.get('levels'):
                for fib_level, fib_price in fib_data['levels'].items():
                    if fib_level in FIBONACCI_WEIGHTS:
                        distance = abs(zone_price - fib_price) / zone_price if zone_price > 0 else 1
                        distance_pct = distance * 100
                        
                        if distance < CONFLUENCE_THRESHOLD:
                            bonus = FIBONACCI_WEIGHTS[fib_level]
                            final = zone.get('score', 0) + bonus
                            print(f"  ✅ MATCH with Fib {fib_level}: Distance={distance_pct:.2f}%")
                            print(f"     Bonus: +{bonus:.1f} → Final Score: {final:.1f}")
                        else:
                            print(f"  ❌ Fib {fib_level}: Distance={distance_pct:.2f}% (too far)")
            print()

asyncio.run(debug_confluence())
