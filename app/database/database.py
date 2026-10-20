# app/database/database.py
from typing import Optional

from anyio import Lock, fail_after, to_thread
from anyio.lowlevel import RunVar
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

_db_lock: RunVar[Lock] = RunVar("db_lock")


def db_lock() -> Lock:
    """
    資料庫工作依序執行的鎖（ADR-0010），每個 event loop 一把。程式隱含依賴「資料庫工作依序執行」（以前卡住
    event loop 等於自動排隊），同時執行會冒出先查再寫、讀快照與訂閱之間等交錯。拿著鎖的工作在 threadpool 裡查
    資料庫，event loop 照常處理 WebSocket。等鎖的請求在 event loop 上等，不佔執行緒也不佔資料庫連線。
    拿著鎖時不可再等另一件也要拿鎖的事（會互相等待而卡死），也不要在鎖裡等外部服務（例如 Google）
    """
    try:
        return _db_lock.get()
    except LookupError:
        lock = Lock()
        _db_lock.set(lock)
        return lock


async def get_db():
    # 整個請求拿著鎖：FastAPI 把一個請求拆成好幾段丟進 threadpool（dependency、端點本體、收尾），
    # 依序執行的單位要是整個請求，段與段之間不能插進別的請求
    async with db_lock():
        db = await to_thread.run_sync(SessionLocal)
        try:
            yield db
        finally:
            await to_thread.run_sync(db.close)


async def run_db(fn, *args, lock_timeout: Optional[float] = None):
    """
    不經 get_db 的資料庫工作（WebSocket、背景工作、/auth/google 的資料庫那段）一律經這裡：拿著 db_lock() 在
    threadpool 執行 fn(*args)，回傳結果。勿只用 run_in_threadpool：不拿鎖會和其他資料庫工作同時執行（ADR-0010）。
    lock_timeout：最多等鎖幾秒，等不到丟 TimeoutError；None 為不限
    """
    lock = db_lock()
    with fail_after(lock_timeout):
        await lock.acquire()
    try:
        return await to_thread.run_sync(fn, *args)
    finally:
        lock.release()
