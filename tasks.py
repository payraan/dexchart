import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import Config
from analysis_engine import AnalysisEngine
from ai_analyzer import ai_analyzer
import httpx

# Import the pre-configured celery_app from our new central file
from celery_app import celery_app

# Initialize bot for tasks
bot = Bot(token=Config.BOT_TOKEN)

@celery_app.task(name="tasks.generate_chart_task")
def generate_chart_task(chat_id: int, message_id: int, token_address: str, timeframe: str, aggregate: str):
    """Generate chart in background worker"""
    return asyncio.run(
        async_generate_chart(chat_id, message_id, token_address, timeframe, aggregate)
    )

async def async_generate_chart(chat_id: int, message_id: int, token_address: str, timeframe: str, aggregate: str):
    """Async chart generation logic"""
    try:
        analysis_engine = AnalysisEngine()
        display_name = f"{aggregate}{timeframe[0].upper()}"
        
        search_url = f"https://api.geckoterminal.com/api/v2/search/pools?query={token_address}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(search_url)
            if response.status_code != 200:
                await bot.send_message(chat_id, f"❌ API Error: {response.status_code}", reply_to_message_id=message_id)
                return "API Error"
                
            pools = response.json().get('data', [])
            if not pools:
                await bot.send_message(chat_id, "❌ Token not found", reply_to_message_id=message_id)
                return "Pool not found"
        
        best_pool = pools[0]
        max_volume = 0
        for pool in pools:
            try:
                volume = float(pool.get('attributes', {}).get('volume_usd', {}).get('h24', 0))
                if volume > max_volume:
                    max_volume = volume
                    best_pool = pool
            except:
                continue
                
        pool_id = best_pool['id']
        
        symbol = "Unknown"
        try:
            relationships = best_pool.get('relationships', {})
            base_token = relationships.get('base_token', {}).get('data', {})
            if base_token:
                symbol = base_token.get('id', '').split('_')[-1]
            if symbol == "Unknown" or not symbol:
                attributes = best_pool.get('attributes', {})
                symbol = attributes.get('name', 'Unknown').split('/')[0]
        except:
            symbol = "Unknown"
        
        analysis_result = await analysis_engine.perform_full_analysis(
            pool_id, token_address, timeframe, aggregate, symbol
        )
        
        if not analysis_result:
            await bot.send_message(chat_id, "❌ Analysis failed", reply_to_message_id=message_id)
            return "Analysis failed"
            
        chart_image = await analysis_engine.create_chart(analysis_result)
        if not chart_image:
            await bot.send_message(chat_id, "❌ Chart generation failed", reply_to_message_id=message_id)
            return "Chart generation failed"
        
        keyboard = [[
            InlineKeyboardButton(
                "🧠 دریافت سیگنال هوش مصنوعی",
                callback_data=f"ai_analyze|{token_address}|{timeframe}|{aggregate}"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await bot.send_photo(
            chat_id=chat_id,
            photo=chart_image,
            caption=f"📊 {symbol} {display_name} Chart\nContract: `{token_address}`",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        return f"Chart for {symbol} sent successfully"
        
    except Exception as e:
        print(f"ERROR in generate_chart_task: {e}")
        await bot.send_message(chat_id, f"❌ Error: {e}", reply_to_message_id=message_id)
        return str(e)

@celery_app.task(name="tasks.ai_analysis_task")
def ai_analysis_task(chat_id: int, message_id: int, token_address: str, timeframe: str, aggregate: str):
    """AI analysis in background worker"""
    return asyncio.run(
        async_ai_analysis(chat_id, message_id, token_address, timeframe, aggregate)
    )

async def async_ai_analysis(chat_id: int, message_id: int, token_address: str, timeframe: str, aggregate: str):
    """Async AI analysis logic"""
    try:
        search_url = f"https://api.geckoterminal.com/api/v2/search/pools?query={token_address}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(search_url)
            if response.status_code != 200:
                await bot.send_message(chat_id, "❌ Token not found for AI analysis", reply_to_message_id=message_id)
                return "Token not found"
                
            pools = response.json().get('data', [])
            if not pools:
                await bot.send_message(chat_id, "❌ Pool not found", reply_to_message_id=message_id)
                return "Pool not found"
        
        best_pool = pools[0]
        max_volume = 0
        for pool in pools:
            try:
                volume = float(pool.get('attributes', {}).get('volume_usd', {}).get('h24', 0))
                if volume > max_volume:
                    max_volume = volume
                    best_pool = pool
            except:
                continue
                
        pool_id = best_pool['id']
        
        analysis_engine = AnalysisEngine()
        analysis_result = await analysis_engine.perform_full_analysis(
            pool_id, token_address, timeframe, aggregate, "AI Analysis"
        )
        
        if not analysis_result:
            await bot.send_message(chat_id, "❌ Could not generate chart for AI", reply_to_message_id=message_id)
            return "Analysis failed"
            
        chart_image = await analysis_engine.create_chart(analysis_result)
        if not chart_image:
            await bot.send_message(chat_id, "❌ Chart creation failed", reply_to_message_id=message_id)
            return "Chart creation failed"
            
        chart_image_bytes = chart_image.getvalue()
        ai_response = await ai_analyzer.analyze_chart_with_gemini(chart_image_bytes)
        
        await bot.send_message(
            chat_id=chat_id,
            text=ai_response,
            reply_to_message_id=message_id
        )
        
        return "AI analysis completed"
        
    except Exception as e:
        print(f"ERROR in ai_analysis_task: {e}")
        await bot.send_message(chat_id, f"❌ AI Analysis Error: {e}", reply_to_message_id=message_id)
        return str(e)
