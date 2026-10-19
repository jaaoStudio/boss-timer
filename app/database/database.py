# app/database/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from ..config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    # 連不上資料庫主機時最多等 5 秒（預設要等作業系統的 TCP 逾時，約 2 分鐘）：WebSocket 握手與同步 API 都在
    # threadpool 裡查資料庫，故障期間每次都卡住一條執行緒，會拖住其他端點（#76）
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()