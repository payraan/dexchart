import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

class Config:
    # Telegram Bot Settings
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    CHAT_ID = os.getenv("CHAT_ID")
    
    # Database Settings
    DATABASE_URL = os.getenv("DATABASE_URL", "tokens.db")
    
    # Scanner Settings
    SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "300"))
    TRENDING_TOKENS_LIMIT = int(os.getenv("TRENDING_TOKENS_LIMIT", "50"))
    GECKOTERMINAL_RATE_LIMIT = int(os.getenv("GECKOTERMINAL_RATE_LIMIT", "30"))

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)

# Trading configuration
class TradingConfig:
    ZONE_SCORE_MIN = float(os.getenv("ZONE_SCORE_MIN", "4.0"))
    PROXIMITY_THRESHOLD = float(os.getenv("PROXIMITY_THRESHOLD", "0.08"))
    COOLDOWN_HOURS = float(os.getenv("COOLDOWN_HOURS", "0.5"))
    FIBONACCI_TOLERANCE = float(os.getenv("FIBONACCI_TOLERANCE", "0.02"))
