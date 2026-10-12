# app/Dockerfile
FROM python:3.11-slim

# 設置工作目錄
WORKDIR /project

# 安裝系統依賴與 uv
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

# 讓 uv 把虛擬環境建立在專案外 (避免 COPY 時被你電腦本機的 .venv 蓋掉！)
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"

# 複製 uv 會用到的核心檔案
COPY pyproject.toml uv.lock ./

# 一行搞定：完美發揮 uv 極快的 lock 檔解析與安裝
RUN uv sync --frozen --no-dev

# 複製應用程式碼 (這樣會把 app 目錄複製進去)
COPY . .

# 暴露端口
EXPOSE 1254

WORKDIR /project

# 將 Docker 專屬的乾淨虛擬環境加入環境變數
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/project
ENV PYTHONUNBUFFERED=1

# WebSocket 死連線偵測（#43）：伺服器每 20 秒送協定層 ping，20 秒內沒回 pong 就關閉。
# 只有 uvicorn 的 "websockets" 實作會主動送 ping（wsproto / websockets-sansio 只會回應），
# 所以明確指定而不靠 --ws auto 的預設。uvicorn CLI 會讀 UVICORN_* 環境變數，compose 的各份啟動指令都套用。
# ping 間隔須遠小於 Cloudflare 的 WebSocket 閒置上限（100 秒）
ENV UVICORN_WS=websockets \
    UVICORN_WS_PING_INTERVAL=20 \
    UVICORN_WS_PING_TIMEOUT=20

# 啟動命令
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 1254"]