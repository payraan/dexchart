import os
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

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

   # Admin and AI settings  
   ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
   GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Logging configuration
logging.basicConfig(   
   level=logging.INFO,
   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
   handlers=[
       logging.StreamHandler(),
       RotatingFileHandler(
           'bot.log',
           maxBytes=5*1024*1024,  # 5MB max per file
           backupCount=2  # Keep 2 backup files
       )
   ]
)

# Trading configuration
class TradingConfig:
   ZONE_SCORE_MIN = float(os.getenv("ZONE_SCORE_MIN", "2.0"))
   PROXIMITY_THRESHOLD = float(os.getenv("PROXIMITY_THRESHOLD", "0.08"))
   COOLDOWN_HOURS = float(os.getenv("COOLDOWN_HOURS", "2.0"))
   FIBONACCI_TOLERANCE = float(os.getenv("FIBONACCI_TOLERANCE", "0.02"))
   HOLDER_API_KEY = os.getenv("HOLDER_API_KEY")
