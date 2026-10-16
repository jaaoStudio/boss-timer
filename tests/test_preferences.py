"""偏好設定存檔（#68）：同時存兩個不同項目時不能丟掉其中一個。"""
from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql

from app.database import models
from app.services import auth_service


class RecordingSession:
    """只記錄送出的 SQL；正式環境是 PostgreSQL，測試沒有資料庫"""
    def __init__(self):
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def user() -> models.User:
    return models.User(id=42, google_id="g", email="a@example.com", display_name="小明",
                       preferences={"channelViewMode": "overview"}, created_at=datetime.now(timezone.utc))


def compiled(statement):
    return statement.compile(dialect=postgresql.dialect())


def test_preferences_are_merged_in_one_atomic_update():
    # 讀出整份、改一項、整份寫回的話，兩個同時的存檔各自讀到舊的整份，後寫的會丟掉先寫的那一項；
    # 改由資料庫在同一個 UPDATE 裡以 || 合併這次存的項目
    db = RecordingSession()
    auth_service.update_user_preferences(db, user(), {"favoriteBossIds": [1, 2], "notAllowed": True})
    assert len(db.statements) == 1
    statement = compiled(db.statements[0])
    sql = str(statement)
    assert sql.startswith("UPDATE users")
    assert "||" in sql and "jsonb_typeof(users.preferences)" in sql
    # 只送這次存的項目（白名單外的不送），不送讀出的整份
    assert {"favoriteBossIds": [1, 2]} in statement.params.values()
    assert user().preferences not in statement.params.values()


def test_nothing_allowed_writes_nothing():
    db = RecordingSession()
    auth_service.update_user_preferences(db, user(), {"notAllowed": True})
    assert db.statements == []
