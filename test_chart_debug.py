import asyncio
from analysis_engine import AnalysisEngine

async def debug_chart():
    e = AnalysisEngine()
    r = await e.perform_full_analysis('solana_3vu9QTWWxEDNmoqRNEfb9Cvke2xBDJcJ1bdL8coYQSF1', 'minute', '15', 'fatgirls')
    
    if r:
        zones = r['technical_levels']['zones']
        print("📊 Zones to be drawn:")
        print(f"  Tier1 (Gold): {len(zones.get('tier1_critical', []))}")
        print(f"  Tier2 (Purple): {len(zones.get('tier2_major', []))}")
        
        # چک کن که آیا کد رسم اجرا میشه
        print("\n🎨 Creating chart...")
        chart = await e.create_chart(r)
        
        if chart:
            with open('debug_chart.png', 'wb') as f:
                f.write(chart.getvalue())
            print("✅ Saved as debug_chart.png")

asyncio.run(debug_chart())
