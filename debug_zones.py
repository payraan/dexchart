import asyncio
from analysis_engine import AnalysisEngine

async def debug_zones():
    engine = AnalysisEngine()
    
    pool_id = "solana_HJtdALk2oebbBJibixu6aFCoKUjQFUZjKDFvjoYZPxUa"
    symbol = "DEBUG"
    
    print("🔍 Debugging zone detection...")
    result = await engine.perform_full_analysis(pool_id, "minute", "5", symbol)
    
    if result:
        zones = result['technical_levels']['zones']
        
        # نمایش همه zones خام
        print("\n📦 RAW ZONES:")
        print(f"Supply zones: {len(zones.get('supply', []))}")
        print(f"Demand zones: {len(zones.get('demand', []))}")
        print(f"Origin zone: {'YES' if zones.get('origin') else 'NO'}")
        
        # نمایش جزئیات
        for s in zones.get('supply', [])[:3]:
            print(f"  Supply: ${s.get('level_price', 0):.8f} (Score: {s.get('score', 0):.1f})")
            
        for d in zones.get('demand', [])[:3]:
            print(f"  Demand: ${d.get('level_price', 0):.8f} (Score: {d.get('score', 0):.1f})")
        
        # بررسی فیبوناچی
        fib = result['technical_levels'].get('fibonacci')
        if fib and fib.get('levels'):
            print("\n📐 FIBONACCI LEVELS:")
            for level, price in fib['levels'].items():
                if level in [0.382, 0.5, 0.618]:
                    print(f"  Fib {level}: ${price:.8f}")
        
        # اطلاعات قیمت
        current_price = result['raw_data']['current_price']
        df = result['raw_data']['dataframe']
        print(f"\n💰 Current Price: ${current_price:.8f}")
        print(f"📊 Data points: {len(df)}")
        print(f"🕐 Age: {(df['timestamp'].iloc[-1] - df['timestamp'].iloc[0])/3600:.1f} hours")

asyncio.run(debug_zones())
