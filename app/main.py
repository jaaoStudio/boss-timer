from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
import json
import os

from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from anyio import to_thread

from app.dependencies import configure_database_lane, limiter, rate_limit_exceeded_handler
from app.routers.system import read_maintenance_file
from app.config import settings
from app.routers import rooms, bosses, auth, websocket, system, feedback # 引入 admin
from app.tasks.cleanup import cleanup_inactive_rooms
from app.websocket.manager import ConnectionManager
from app.dependencies import get_connection_manager

# 設定檔的路徑 (與 system.py 中的路徑保持一致)

# 用於追蹤上次讀取的維護狀態
last_maintenance_status = {"is_maintenance": False, "is_ready_for_maintenance": False, "title": "", "message": ""}

async def check_maintenance_mode(manager: ConnectionManager = Depends(get_connection_manager)):
    """
    檢查系統是否處於維護模式。如果是，則拋出 503 錯誤。
    並在狀態變化時透過 WebSocket 廣播。
    """
    global last_maintenance_status
    # 讀檔走資料庫通道：與管理員寫檔依序執行，不會讀到寫到一半的檔案（ADR-0010）
    data = await to_thread.run_sync(read_maintenance_file) or {}
    current_maintenance_status = {
        "is_maintenance": data.get("is_maintenance", False),
        "is_ready_for_maintenance": data.get("is_ready_for_maintenance", False),
        "title": data.get("title", ""),
        "message": data.get("message", ""),
    }

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
    configure_database_lane()
    cleanup_task = asyncio.create_task(cleanup_inactive_rooms())
    heartbeat_task = asyncio.create_task(get_connection_manager().run_heartbeat())
    yield
    cleanup_task.cancel()
    heartbeat_task.cancel()

app = FastAPI(title="Boss Tracker API", version=settings.version, lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

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
app.include_router(feedback.router, dependencies=[Depends(check_maintenance_mode)])

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.version,
        "service": "boss_service"
    }

if __name__ == "__main__":
    import uvicorn
    # 僅供本機直接執行；正式環境的 WebSocket ping 設定以 app/Dockerfile 的 UVICORN_WS* 為準（ADR-0008）
    uvicorn.run(app, host="0.0.0.0", port=1254, root_path="/api", proxy_headers=True, forwarded_allow_ips="*")