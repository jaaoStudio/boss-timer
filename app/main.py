from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
import json
import os

from app.config import settings
from app.routers import rooms, bosses, auth, websocket, system # 引入 admin
from app.tasks.cleanup import cleanup_inactive_rooms
from app.websocket.manager import ConnectionManager
from app.dependencies import get_connection_manager

# 設定檔的路徑 (與 system.py 中的路徑保持一致)
MAINTENANCE_FILE_PATH = os.path.join(os.path.dirname(__file__), "maintenance.json")

# 用於追蹤上次讀取的維護狀態
last_maintenance_status = {"is_maintenance": False, "is_ready_for_maintenance": False, "title": "", "message": ""}

async def check_maintenance_mode(manager: ConnectionManager = Depends(get_connection_manager)):
    """
    檢查系統是否處於維護模式。如果是，則拋出 503 錯誤。
    並在狀態變化時透過 WebSocket 廣播。
    """
    global last_maintenance_status
    current_maintenance_status = {"is_maintenance": False, "is_ready_for_maintenance": False, "title": "", "message": ""}
    if os.path.exists(MAINTENANCE_FILE_PATH):
        try:
            with open(MAINTENANCE_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                current_maintenance_status = {
                    "is_maintenance": data.get("is_maintenance", False),
                    "is_ready_for_maintenance": data.get("is_ready_for_maintenance", False),
                    "title": data.get("title", ""),
                    "message": data.get("message", "")
                }
        except (json.JSONDecodeError, IOError):
            pass # 檔案讀取或解析失敗，使用預設值

    # 檢查狀態是否發生變化
    if current_maintenance_status != last_maintenance_status:
        logging.info(f"Maintenance status changed: {current_maintenance_status}")
        # 廣播維護狀態給所有客戶端
        await manager.broadcast_to_all({
            "type": "maintenance_status_update",
            "data": current_maintenance_status
        })
        last_maintenance_status = current_maintenance_status

    if current_maintenance_status["is_maintenance"]:
        raise HTTPException(status_code=503, detail="Service Unavailable")

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
    allow_origins=origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊路由
# 將 check_maintenance_mode 應用到所有路由，除了 system.router 中的 /maintenance-info
app.include_router(rooms.router, dependencies=[Depends(check_maintenance_mode)])
app.include_router(bosses.router, dependencies=[Depends(check_maintenance_mode)])
app.include_router(auth.router) # auth.router 不受維護模式影響
app.include_router(websocket.router, dependencies=[Depends(check_maintenance_mode)])
app.include_router(system.router) # system.router 不受維護模式影響

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