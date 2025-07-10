# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging

from app.config import settings
from app.routers import rooms, bosses, auth, websocket
from app.tasks.cleanup import cleanup_inactive_rooms
from app.websocket.manager import ConnectionManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = asyncio.create_task(cleanup_inactive_rooms())
    yield
    cleanup_task.cancel()

app = FastAPI(title="Boss Tracker API", version=settings.version, lifespan=lifespan)

# CORS 設定
origin_list = [origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊路由
app.include_router(rooms.router)
app.include_router(bosses.router)
app.include_router(auth.router)
app.include_router(websocket.router)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.version,
        "service": "boss_service"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=1254, root_path="/api")