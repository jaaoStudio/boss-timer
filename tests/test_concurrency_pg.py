"""
同時執行的請求在 PostgreSQL 上的競爭（PR #80：端點改在 threadpool 執行後，請求會真的同時跑）。
需要真的 PostgreSQL：設定 TEST_DATABASE_URL 才執行（例如臨時容器），平常跳過。
"""
import os
import threading
import uuid

import pytest
from sqlalchemy import create_engine, func, inspect
from sqlalchemy.orm import sessionmaker

from app.database import models
from app.database.database import Base
from app.schemas import auth as auth_schemas
from app.schemas.feedback import FeedbackCreate
from app.services import auth_service
from app.services.feedback_service import DAILY_SUBMIT_LIMIT, FeedbackRateLimited, FeedbackService

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="需要 PostgreSQL（設定 TEST_DATABASE_URL）")


@pytest.fixture(scope="module")
def Session():
    engine = create_engine(URL, pool_size=20)
    # 只在空的資料庫上跑：不小心指到開發資料庫時不建表、不刪表
    if inspect(engine).get_table_names():
        engine.dispose()
        pytest.fail("TEST_DATABASE_URL 要指向空的資料庫（例如臨時容器），這個資料庫已經有資料表")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    Base.metadata.drop_all(engine)
    engine.dispose()


def at_once(Session, n, fn):
    """
    n 個執行緒同時執行 fn(db, i)，回傳每個的結果或例外。照正式環境的 get_db，每個執行緒用完就關閉 session
    （交易與鎖一併結束）
    """
    barrier = threading.Barrier(n)
    results = [None] * n

    def run(i):
        barrier.wait()
        try:
            with Session() as db:
                results[i] = fn(db, i)
        except Exception as e:   # noqa: BLE001  測試要看到每個執行緒的例外
            results[i] = e

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def new_user(Session):
    with Session() as db:
        user = models.User(google_id=str(uuid.uuid4()), email=f"{uuid.uuid4()}@example.com", display_name="u", preferences={})
        db.add(user)
        db.commit()
        return user.id


def test_double_vote_does_not_500(Session):
    user_id = new_user(Session)
    with Session() as db:
        item = models.FeedbackItem(type="feature", title="t", status="open", created_by=user_id)
        db.add(item)
        db.commit()
        item_id = item.id
    for _ in range(10):
        results = at_once(Session, 2, lambda db, i: FeedbackService.toggle_vote(db, user_id, item_id))
        assert not [r for r in results if isinstance(r, Exception)], results


def test_daily_limit_holds_under_concurrent_submissions(Session):
    user_id = new_user(Session)
    for _ in range(DAILY_SUBMIT_LIMIT - 1):
        with Session() as db:
            FeedbackService.create_feedback(db, user_id, FeedbackCreate(type="bug", title="t"))
    results = at_once(Session, 5, lambda db, i: FeedbackService.create_feedback(db, user_id, FeedbackCreate(type="bug", title="t")))
    assert all(isinstance(r, FeedbackRateLimited) or not isinstance(r, Exception) for r in results), results
    with Session() as db:
        count = db.query(func.count(models.FeedbackItem.id)).filter(models.FeedbackItem.created_by == user_id).scalar()
    assert count == DAILY_SUBMIT_LIMIT


def test_first_login_sent_twice_creates_one_user(Session):
    google_id = str(uuid.uuid4())
    data = auth_schemas.UserCreate(google_id=google_id, email=f"{google_id}@example.com", display_name="u")
    results = at_once(Session, 2, lambda db, i: auth_service.create_user(db, data).id)
    assert not [r for r in results if isinstance(r, Exception)], results
    assert results[0] == results[1]


def test_concurrent_logins_keep_one_refresh_token(Session):
    user_id = new_user(Session)
    for _ in range(5):
        tokens = [auth_service.create_refresh_token(data={"sub": str(user_id)}) for _ in range(3)]
        results = at_once(Session, 3, lambda db, i: auth_service.save_refresh_token(db, user_id, tokens[i]))
        assert not [r for r in results if isinstance(r, Exception)], results
        with Session() as db:
            assert db.query(models.RefreshToken).filter(models.RefreshToken.user_id == user_id).count() == 1
