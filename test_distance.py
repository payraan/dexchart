import asyncio
from analysis_engine import AnalysisEngine
from zone_config import CONFLUENCE_THRESHOLD

async def test_distance():
    e = AnalysisEngine()
    
    # مقادیر دقیق
    zone_price = 0.00046060
    fib_618 = 0.00042251
    
    # محاسبه فاصله
    distance = abs(zone_price - fib_618) / zone_price
    distance_pct = distance * 100
    
    print(f"Zone: ${zone_price:.8f}")
    print(f"Fib 0.618: ${fib_618:.8f}")
    print(f"Distance: {distance_pct:.2f}%")
    print(f"Threshold: {CONFLUENCE_THRESHOLD*100:.1f}%")
    print(f"Match: {'YES ✅' if distance < CONFLUENCE_THRESHOLD else 'NO ❌'}")
    
    # تست با آستانه‌های مختلف
    print("\nWith different thresholds:")
    for t in [0.05, 0.10, 0.15]:
        print(f"  {t*100:.0f}%: {'✅' if distance < t else '❌'}")

asyncio.run(test_distance())
