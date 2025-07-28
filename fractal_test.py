import numpy as np

def find_fractals(highs, lows, period=5):
    """
    پیدا کردن فرکتال‌های 5 کندلی
    fractal_high: کندل وسط بالاترین high را دارد
    fractal_low: کندل وسط پایین‌ترین low را دارد
    """
    supply_fractals = []  # برای سطوح عرضه
    demand_fractals = []  # برای سطوح تقاضا
    
    half_period = period // 2
    
    for i in range(half_period, len(highs) - half_period):
        # بررسی فرکتال عرضه (supply)
        is_fractal_high = True
        center_high = highs[i]
        
        for j in range(i - half_period, i + half_period + 1):
            if j != i and highs[j] >= center_high:
                is_fractal_high = False
                break
        
        if is_fractal_high:
            supply_fractals.append(i)
        
        # بررسی فرکتال تقاضا (demand)  
        is_fractal_low = True
        center_low = lows[i]
        
        for j in range(i - half_period, i + half_period + 1):
            if j != i and lows[j] <= center_low:
                is_fractal_low = False
                break
                
        if is_fractal_low:
            demand_fractals.append(i)
    
    return supply_fractals, demand_fractals

# تست سریع
highs = [10, 12, 15, 13, 11, 14, 16, 12, 10, 11]
lows = [8, 9, 11, 10, 9, 11, 12, 9, 8, 9]

supply, demand = find_fractals(highs, lows)
print(f"Supply fractals: {supply}")
print(f"Demand fractals: {demand}")
