import asyncio
from analysis_engine import AnalysisEngine

async def debug_fibs():
    e = AnalysisEngine()
    r = await e.perform_full_analysis('solana_3vu9QTWWxEDNmoqRNEfb9Cvke2xBDJcJ1bdL8coYQSF1', 'minute', '15', 'fatgirls')
    
    if r:
        zones = r['technical_levels']['zones']
        
        # چک کن که آیا matched_fibs ذخیره شده
        for tier2 in zones.get('tier2_major', []):
            print(f"Tier2 Zone at ${tier2.get('level_price', 0):.8f}")
            print(f"  Matched Fibs: {tier2.get('matched_fibs', [])}")
            print(f"  Is Confluence: {tier2.get('is_confluence', False)}")
        
        # چک کن فیبوناچی‌ها
        fib_data = r['technical_levels'].get('fibonacci', {})
        if fib_data and fib_data.get('levels'):
            print("\nFibonacci levels:")
            for level, price in fib_data['levels'].items():
                if level in [0.382, 0.5, 0.618]:
                    print(f"  Fib {level}: ${price:.8f}")

asyncio.run(debug_fibs())
