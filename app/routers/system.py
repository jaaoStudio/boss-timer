
import contextlib
import json
import tempfile
from anyio import from_thread
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, ValidationError
import os
import logging

from app.config import settings
from app.database import models
from app.websocket.manager import ConnectionManager
from app.dependencies import get_current_admin_user, get_connection_manager, rate_limit

class MaintenanceInfo(BaseModel):
    is_maintenance: bool = False
    is_ready_for_maintenance: bool = False
    title: str = ""
    message: str = ""

class MaintenanceConfigUpdate(BaseModel):
    is_maintenance: bool
    is_ready_for_maintenance: bool
    title: str
    message: str

# 正式機以 MAINTENANCE_FILE 指到掛載的目錄裡，blue / green 共用主機上同一份（#81）；沒設定時用專案裡的檔案
MAINTENANCE_FILE_PATH = settings.maintenance_file or os.path.join(os.path.dirname(__file__), "..", "maintenance.json")


router = APIRouter(prefix="/system", tags=["system"])
def read_maintenance_file() -> Optional[dict]:
    """
    讀 maintenance.json：不存在回傳 {}（沒有維護），讀取或格式錯誤回傳 None（狀態不明）。
    在 event loop 上呼叫（檔案很小）；程式寫入以換檔完成，不會讀到一半
    """
    try:
        with open(MAINTENANCE_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


# 上次讀到的維護狀態：變了才廣播
last_maintenance_status = MaintenanceInfo().model_dump()


async def refresh_maintenance_status(manager: ConnectionManager) -> dict:
    """
    讀維護狀態，跟上次不同就廣播。所有維護狀態的讀取與廣播都經這裡（受保護的請求、/maintenance-info、後台切換），同一個變化只廣播一次（#86）。
    在 event loop 上直接讀（檔案很小，寫入以換檔完成不會讀到一半）。廣播前就記下：同時的請求不會重複廣播；
    廣播失敗時還原，下一個請求會重試
    """
    global last_maintenance_status
    data = read_maintenance_file()
    try:
        # 缺的欄位補預設值；手動改檔寫錯型別（"title": null）時不放行也不回 500。受保護的路由與 /maintenance-info 用同一份驗證過的值
        current = MaintenanceInfo.model_validate(data).model_dump()
    except ValidationError:
        return last_maintenance_status   # 讀到一半、格式或型別錯誤：沿用上次的狀態，不當成「沒有維護」；檔案不存在才是沒有維護
    if current != last_maintenance_status:
        previous, last_maintenance_status = last_maintenance_status, current
        logging.info(f"Maintenance status changed: {current}")
        try:
            await manager.broadcast_to_all({"type": "maintenance_status_update", "data": current})
        except BaseException:
            if last_maintenance_status is current:   # 期間沒有更新的狀態才還原
                last_maintenance_status = previous
            raise
    return current


async def check_maintenance_mode(manager: ConnectionManager = Depends(get_connection_manager)):
    """受保護路由的 dependency：維護中回 503；狀態變化時廣播"""
    if (await refresh_maintenance_status(manager))["is_maintenance"]:
        raise HTTPException(status_code=503, detail="Service Unavailable")


@router.get("/maintenance-info", response_model=MaintenanceInfo, dependencies=[rate_limit("60/minute")])
async def get_maintenance_info(manager: ConnectionManager = Depends(get_connection_manager)):
    """
    獲取系統維護公告資訊：與受保護的路由同一個來源（refresh_maintenance_status），讀檔失敗時兩者一致
    """
    info = await refresh_maintenance_status(manager)
    if info["is_maintenance"] or info["is_ready_for_maintenance"]:
        return info
    return {"is_maintenance": False, "is_ready_for_maintenance": False, "title": "", "message": "everything all good."}


def save_maintenance_config(data: dict) -> None:
    """
    寫暫存檔、fsync 後換上（os.replace）：另一個 slot 或主機上同時讀的人只會讀到舊檔或新檔，不會讀到寫一半、
    誤判成「沒有維護」並廣播；斷電後也不會是空檔。正式機掛的是目錄而不是單一檔案，才能換檔（#81）
    """
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MAINTENANCE_FILE_PATH), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # 容器以 root 執行：沿用原檔的擁有者與權限，主機上不用 sudo 也能改（mkstemp 預設 root、600）
        try:
            st = os.stat(MAINTENANCE_FILE_PATH)
            os.chmod(tmp, st.st_mode & 0o777)
            with contextlib.suppress(PermissionError):   # 不是 root 時只能維持自己擁有，不因此存檔失敗
                os.chown(tmp, st.st_uid, st.st_gid)
        except FileNotFoundError:
            os.chmod(tmp, 0o644)
        os.replace(tmp, MAINTENANCE_FILE_PATH)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


@router.post("/maintenance-config", response_model=MaintenanceConfigUpdate, dependencies=[rate_limit("10/minute")])
def update_maintenance_config(
    config: MaintenanceConfigUpdate,
    current_user: models.User = Depends(get_current_admin_user),
    manager: ConnectionManager = Depends(get_connection_manager)
):
    """
    更新系統維護配置。
    只有管理員可以訪問此端點。
    """
    try:
        save_maintenance_config(config.model_dump())
        logging.info(f"Maintenance config updated by admin {current_user.email}: {config.model_dump()}")

        # 立即廣播：同步端點在 threadpool 執行，回到 event loop 上（ADR-0010）
        from_thread.run(refresh_maintenance_status, manager)

        return config
    except Exception as e:
        logging.error(f"Failed to update maintenance config: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update maintenance config")
