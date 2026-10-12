import os

# 測試不連資料庫、不呼叫 Google，只需要讓設定能載入
for key, value in {
    "GOOGLE_CLIENT_ID": "test",
    "GOOGLE_CLIENT_SECRET": "test",
    "DB_USER": "test",
    "DB_PASSWORD": "test",
    "DB_HOST": "localhost",
    "DB_NAME": "test",
}.items():
    os.environ.setdefault(key, value)


import pytest  # noqa: E402  設定環境變數後才載入 app


@pytest.fixture(autouse=True)
def reset_limiter():
    from app.dependencies import limiter
    limiter.reset()
