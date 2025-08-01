from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/health")
def health_check():
    bot_token_exists = bool(os.getenv("BOT_TOKEN"))
    return {
        "status": "ok",
        "message": "Minimal health check is running successfully!",
        "bot_token_found": bot_token_exists
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
