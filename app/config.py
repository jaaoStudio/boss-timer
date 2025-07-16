from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import ClassVar

import os

load_dotenv()

class Settings(BaseSettings):
    # 資料庫配置
    DB_USER: str = os.getenv("DB_USER")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    DB_HOST: str = os.getenv("DB_HOST")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME")

    # JWT 配置
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # CORS 配置
    allowed_origins: str = os.getenv("ALLOWED_ORIGINS", "")

    # Google Auth
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID")

    # 應用配置
    version: str = os.getenv("VERSION", "1.0.0")

    remote_registry_ip: str
    env: str

    class Config:
        env_file = ".env"

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
