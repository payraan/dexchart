# zone_config.py - تنظیمات الگوریتم تشخیص نواحی

# Origin Zone Parameters
ORIGIN_CONSOLIDATION_MIN = 20  # حداقل تعداد کندل در محدوده تجمع
ORIGIN_RANGE_MAX = 0.5  # حداکثر نوسان 50% در محدوده
ORIGIN_PUMP_MIN = 0.5  # حداقل پامپ 50% بعد از Origin

# Major Zone Parameters  
MAX_MAJOR_ZONES = 7  # حداکثر تعداد Major Zones
MIN_ZONE_SCORE = 1.5  # حداقل امتیاز برای یک Zone معتبر
ZONE_MERGE_THRESHOLD = 1.0  # ضریب ATR برای ادغام zones نزدیک

# Zone Scoring Weights
WEIGHT_TOUCHES = 0.30  # وزن تعداد برخورد
WEIGHT_REACTION = 0.25  # وزن قدرت واکنش
WEIGHT_VOLUME = 0.20  # وزن حجم
WEIGHT_SR_FLIP = 0.15  # وزن تبدیل S/R
WEIGHT_FIBONACCI = 0.10  # وزن همخوانی فیبوناچی

# Visual Settings
ORIGIN_ZONE_COLOR = '#FF9500'  # نارنجی iOS
ORIGIN_ZONE_ALPHA = 0.30
MAJOR_ZONE_COLOR = '#007AFF'  # آبی iOS  
MAJOR_ZONE_ALPHA = 0.25
