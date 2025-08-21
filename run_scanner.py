print("DEBUG: Attempting to start run_scanner.py...")
#!/usr/bin/env python3
import asyncio
import logging
from config import Config
from background_scanner import BackgroundScanner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    """Initialize and start the background scanner worker"""
    logging.info("🚀 Starting Scanner Worker...")
    
    scanner = BackgroundScanner(
        bot_token=Config.BOT_TOKEN,
        chat_id=Config.CHAT_ID
    )
    
    # Start scanning - this will run indefinitely
    await scanner.start_scanning()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Scanner worker stopped by user")
    except Exception as e:
        logging.error(f"❌ Scanner worker error: {e}", exc_info=True)
