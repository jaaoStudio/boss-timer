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
    # 資料庫連不上或網路中斷時，不讓查詢卡住執行緒好幾分鐘（#76）：
    # - connect_timeout：建立新連線最多等 5 秒（預設要等作業系統的 TCP 逾時，約 2 分鐘）
    # - tcp_user_timeout / keepalives：已經在連線池裡的連線遇到封包被丟掉時，送出的資料 10 秒沒有回應就放棄
    #   （預設要等 TCP 重傳逾時，約 15 分鐘；pool_pre_ping 的 SELECT 1 就會卡在這裡）
    connect_args={
        "connect_timeout": 5,
        "tcp_user_timeout": 10_000,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    },
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()