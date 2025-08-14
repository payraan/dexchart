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

# Confluence Detection Settings
CONFLUENCE_THRESHOLD = 0.035  # 1.5% tolerance
FIBONACCI_WEIGHTS = {
    0.618: 2.5,  # Golden Ratio
    0.382: 2.0,
    0.500: 1.8,
    0.786: 1.5,
    0.236: 1.2
}

# Zone Tier Thresholds
TIER1_SCORE_THRESHOLD = 7.0
TIER2_SCORE_THRESHOLD = 3.0

# Zone Colors
TIER1_COLOR = '#FFD700'  # طلایی
TIER1_ALPHA = 0.35

# Signal Detection Thresholds
TIER1_APPROACH_THRESHOLD = 0.02   # 2% for approaching
TIER1_BREAKOUT_THRESHOLD = 0.005  # 0.5% for breakout confirmation
TIER1_COOLDOWN_DISTANCE = 0.05    # 5% to reset state

TIER2_APPROACH_THRESHOLD = 0.015  # 1.5%
TIER2_BREAKOUT_THRESHOLD = 0.01   # 1%
TIER2_COOLDOWN_DISTANCE = 0.03    # 3%

# Zone States
ZONE_STATES = {
    'IDLE': 'Far from zone',
    'APPROACHING_UP': 'Approaching from below',
    'APPROACHING_DOWN': 'Approaching from above',
    'TESTING': 'Testing zone',
    'BROKEN_UP': 'Broken upwards',
    'BROKEN_DOWN': 'Broken downwards',
    'COOLDOWN': 'In cooldown period'
}

# Signal Priority Scores
SIGNAL_PRIORITY = {
    'ORIGIN_ZONE': 10,
    'TIER1_BREAKOUT': 9,
    'TIER1_APPROACHING': 7,
    'TIER2_BREAKOUT': 5,
    'TIER2_APPROACHING': 3
}
