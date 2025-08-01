from fastapi import FastAPI
from config import Config

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok", "bot_configured": bool(Config.BOT_TOKEN)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
