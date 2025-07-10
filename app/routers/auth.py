# app/routers/auth.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database.database import get_db
from app.services.room_service import RoomService
from app.schemas.room import RoomResponse, RoomExists
from app.utils.jwt_helper import create_access_token
import logging

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", tags=["Authentication"])
async def login_for_access_token(response: Response):
    """
    Generate a new JWT for an anonymous user and set it in an HttpOnly cookie.
    """
    user_id = str(uuid.uuid4())
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user_id}, expires_delta=access_token_expires
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite='lax',
        secure=True,
        max_age=settings.access_token_expire_minutes * 60
    )
    return {"access_token": access_token, "token_type": "bearer"}