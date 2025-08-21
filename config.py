# config.py
import os
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

print("DEBUG: [OK] Starting config.py execution...")

# Load environment variables from .env file
load_dotenv()

class Config:
    # Telegram Bot Settings
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    CHAT_ID = os.getenv("CHAT_ID")
    
    # Database Settings
    DATABASE_URL = os.getenv("DATABASE_URL", "tokens.db")
    
    # Scanner Settings - Safely convert to int
    SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL") or "300")
    TRENDING_TOKENS_LIMIT = int(os.getenv("TRENDING_TOKENS_LIMIT") or "50")
    GECKOTERMINAL_RATE_LIMIT = int(os.getenv("GECKOTERMINAL_RATE_LIMIT") or "30")
    
    # Admin and AI settings
    ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
    ADMIN_IDS = [int(x) for x in ADMIN_IDS_STR.split(",") if x.strip().isdigit()]
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Logging configuration
logging.basicConfig(   
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            'bot.log',
            maxBytes=5*1024*1024,
            backupCount=2
        )
    ]
)

# Trading configuration
class TradingConfig:
    # Safely convert to float
    ZONE_SCORE_MIN = float(os.getenv("ZONE_SCORE_MIN") or "2.0")
    PROXIMITY_THRESHOLD = float(os.getenv("PROXIMITY_THRESHOLD") or "0.08")
    COOLDOWN_HOURS = float(os.getenv("COOLDOWN_HOURS") or "2.0")
    FIBONACCI_TOLERANCE = float(os.getenv("FIBONACCI_TOLERANCE") or "0.02")
    HOLDER_API_KEY = os.getenv("HOLDER_API_KEY")

print("DEBUG: [OK] Finished config.py execution.")
