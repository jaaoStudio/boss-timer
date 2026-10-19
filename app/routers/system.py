
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel
import os
import logging

from app.database import models
from app.websocket.manager import ConnectionManager
from app.dependencies import get_current_admin_user, get_connection_manager, rate_limit

class MaintenanceInfo(BaseModel):
    is_maintenance: bool
    is_ready_for_maintenance: bool
    title: str
    message: str

class MaintenanceConfigUpdate(BaseModel):
    is_maintenance: bool
    is_ready_for_maintenance: bool
    title: str
    message: str

# 設定檔的路徑
MAINTENANCE_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "maintenance.json")


router = APIRouter(prefix="/system", tags=["system"])
def read_maintenance_file() -> Optional[dict]:
    """
    讀 maintenance.json，沒有或格式錯誤時回傳 None。同步：在資料庫通道裡執行（ADR-0010），與管理員寫檔依序執行，
    不會讀到寫到一半的檔案（先清空再寫入時同時讀到一半，會誤判成「沒有維護」並廣播出去）
    """
    if not os.path.exists(MAINTENANCE_FILE_PATH):
        return None
    try:
        with open(MAINTENANCE_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None
    return data if isinstance(data, dict) else None


@router.get("/maintenance-info", response_model=MaintenanceInfo)
@rate_limit("60/minute")
def get_maintenance_info(request: Request):
    """
    獲取系統維護公告資訊。
    從 maintenance.json 檔案動態讀取。
    """
    default_info = {"is_maintenance": False, "is_ready_for_maintenance": False, "title": "", "message": ""}
    data = read_maintenance_file()
    # 確保所有必要的鍵都存在
    if data is None or not all(key in data for key in ["is_maintenance", "is_ready_for_maintenance", "title", "message"]):
        return default_info
    if data["is_maintenance"] or data["is_ready_for_maintenance"]:
        return data
    return {"is_maintenance": False, "is_ready_for_maintenance": False, "title": "", "message": "everything all good."}


def _write_maintenance_file(data: dict) -> None:
    with open(MAINTENANCE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.post("/maintenance-config", response_model=MaintenanceConfigUpdate)
@rate_limit("10/minute")
def update_maintenance_config(
    request: Request,
    config: MaintenanceConfigUpdate,
    current_user: models.User = Depends(get_current_admin_user),
    manager: ConnectionManager = Depends(get_connection_manager)
):
    """
    更新系統維護配置。
    只有管理員可以訪問此端點。
    """
    try:
        # 在資料庫通道裡寫，與讀取依序執行（read_maintenance_file）
        _write_maintenance_file(config.model_dump())
        logging.info(f"Maintenance config updated by admin {current_user.email}: {config.model_dump()}")

        # 立即透過 WebSocket 廣播更新的狀態：同步端點在 threadpool 執行，回到 event loop 上廣播（ADR-0010）
        manager.broadcast_to_all_from_thread({
            "type": "maintenance_status_update",
            "data": config.model_dump()
        })

        return config
    except Exception as e:
        logging.error(f"Failed to update maintenance config: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update maintenance config")
