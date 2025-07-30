# app/Dockerfile
FROM python:3.11-slim

# 設置工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

COPY requirements.txt ./requirements.txt

# --system 參數會將套件安裝到全域環境中，這是在 Docker 中的標準作法
RUN uv pip install --no-cache-dir -r requirements.txt --system

# 複製應用程式碼
# 複製當前目錄所有內容到工作目錄中
COPY . .

# 暴露端口
EXPOSE 1254

WORKDIR /

# 設置環境變量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 啟動命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "1254"]