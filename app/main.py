from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio


from app.routers.system import check_maintenance_mode
from app.config import settings
from app.routers import rooms, bosses, auth, websocket, system, feedback # 引入 admin
from app.tasks.cleanup import cleanup_inactive_rooms
from app.dependencies import get_connection_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = asyncio.create_task(cleanup_inactive_rooms())
    heartbeat_task = asyncio.create_task(get_connection_manager().run_heartbeat())
    yield
    cleanup_task.cancel()
    heartbeat_task.cancel()

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
# 維護中回 503 的路由（system.check_maintenance_mode）；auth 與 system 不受維護模式影響
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