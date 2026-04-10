# app/routers/bosses.py
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from typing import List

from app.database.database import get_db
from app.database.models import BossType
from app.dependencies import limiter
from app.schemas.boss import BossTypeResponse

router = APIRouter(prefix="/boss", tags=["boss"])


@router.get("/boss-types", response_model=List[BossTypeResponse])
@limiter.limit("5/minute")
async def get_boss_types(request: Request, db: Session = Depends(get_db)):
    return db.query(BossType).all()

