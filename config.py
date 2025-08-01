import os
from dotenv import load_dotenv

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
