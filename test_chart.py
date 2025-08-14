import asyncio
from analysis_engine import AnalysisEngine

async def test_chart():
    engine = AnalysisEngine()
    
    pool_id = "solana_Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE"
    symbol = "SOL"
    
    print(f"🔄 Creating chart for {symbol}...")
    result = await engine.perform_full_analysis(pool_id, "hour", "1", symbol)
    
    if result:
        chart = await engine.create_chart(result)
        if chart:
            # ذخیره چارت
            with open('test_chart.png', 'wb') as f:
                f.write(chart.getvalue())
            print("✅ Chart saved as test_chart.png")
            print("🖼️ Open it with: open test_chart.png")
        else:
            print("❌ Chart creation failed")
    else:
        print("❌ Analysis failed")

asyncio.run(test_chart())
