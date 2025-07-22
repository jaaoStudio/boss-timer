
import json
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
import os
import logging

from app.database import models
from app.websocket.manager import ConnectionManager
from app.dependencies import get_current_admin_user, get_connection_manager

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
@router.get("/maintenance-info", response_model=MaintenanceInfo)
async def get_maintenance_info():
    """
    獲取系統維護公告資訊。
    從 maintenance.json 檔案動態讀取。
    """
    default_info = {"is_maintenance": False, "is_ready_for_maintenance": False, "title": "", "message": ""}

    if not os.path.exists(MAINTENANCE_FILE_PATH):
        return default_info

    try:
        with open(MAINTENANCE_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 確保所有必要的鍵都存在
            if all(key in data for key in ["is_maintenance", "is_ready_for_maintenance", "title", "message"]):
                return data
            else:
                return default_info
    except (json.JSONDecodeError, IOError):
        # 如果檔案讀取或解析失敗，回傳預設的非啟用狀態
        return default_info


@router.put("/maintenance-info")
async def update_maintenance_info(maintenance_info: MaintenanceInfo):
    """
    更新系統維護公告資訊。
    將資訊寫入到 maintenance.json 檔案。
    """
    with open(MAINTENANCE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(maintenance_info.model_dump_json(), f, ensure_ascii=False, indent=4)

    return {"message": "Maintenance info updated successfully."}


@router.post("/maintenance-config", response_model=MaintenanceConfigUpdate)
async def update_maintenance_config(
    config: MaintenanceConfigUpdate,
    current_user: models.User = Depends(get_current_admin_user),
    manager: ConnectionManager = Depends(get_connection_manager)
):
    """
    更新系統維護配置。
    只有管理員可以訪問此端點。
    """
    try:
        # 將新的配置寫入 maintenance.json 檔案
        with open(MAINTENANCE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(), f, ensure_ascii=False, indent=2)
        logging.info(f"Maintenance config updated by admin {current_user.email}: {config.model_dump()}")

        # 立即透過 WebSocket 廣播更新的狀態
        await manager.broadcast_to_all({
            "type": "maintenance_status_update",
            "data": config.model_dump()
        })

        return config
    except Exception as e:
        logging.error(f"Failed to update maintenance config: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update maintenance config")
