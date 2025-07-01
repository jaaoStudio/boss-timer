# backend/Dockerfile
FROM python:3.11-slim

# 設置工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 複製 requirements.txt 並安裝 Python 依賴
# 注意：你的文件名是 requerment.txt (有拼寫錯誤)
COPY requerment.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式碼
COPY boss_tracker.py ./main.py
COPY db_config.py ./

# 暴露端口
EXPOSE 1254

# 設置環境變量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 啟動命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "1254"]