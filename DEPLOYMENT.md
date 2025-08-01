# DexChart Railway Deployment Guide

## Railway Services Setup:

1. **Health Check Service** (Main)
   - Start Command: `uvicorn health_check:app --host 0.0.0.0 --port $PORT`
   - Port: Railway auto-assigns $PORT

2. **Telegram Bot Service**  
   - Start Command: `python telegram_bot.py`

3. **Background Scanner Service**
   - Start Command: `python background_scanner.py`

## Environment Variables:
- BOT_TOKEN
- CHAT_ID  
- DATABASE_URL (Railway PostgreSQL)
- REDIS_URL (Railway Redis)
