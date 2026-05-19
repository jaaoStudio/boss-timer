---
name: Boss Timer 基礎設施與部署規範
description: Docker 架構、Docker Compose 配置 (開發/正式)、Dockerfile 設計、Celery Worker 容器化、環境管理與部署流程。適用於所有 DevOps、部署、容器化相關任務。
---

# Boss Timer 基礎設施與部署規範

## 專案總覽

Boss Timer 採用 Docker 容器化部署，分為開發環境 (本機混合模式) 與正式環境 (全容器化)。  
後端使用 **uv** 作為 Python 套件管理工具，前端使用 **npm**。  
正式環境部署至 **ARM64 架構** 機器，透過 **Harbor Registry** 管理映像。

---

## 套件管理

### 後端 (Python — uv)
- **定義檔**: `pyproject.toml` (位於專案根目錄)
- **鎖定檔**: `uv.lock` (位於專案根目錄)
- **新增套件**: `uv add <package>`
- **同步環境**: `uv sync`
- **執行指令**: `uv run <command>`
- ⚠️ **已棄用 `requirements.txt`**，Docker 內使用 `uv sync` 安裝

### 前端 (Node.js — npm)
- **定義檔**: `frontend/package.json`
- **鎖定檔**: `frontend/package-lock.json`
- **安裝**: `npm ci`
- **開發**: `npm run dev`
- **建置**: `npm run build`

---

## 專案根目錄檔案結構

```
boss-timing/
├── .env                       # Docker Compose 變數 (REMOTE_REGISTRY_IP, BACKEND_VERSION, FRONTEND_VERSION)
├── .dockerignore               # 根目錄 Docker 排除規則
├── pyproject.toml              # Python 套件定義 (uv)
├── uv.lock                    # Python 套件鎖定 (uv)
├── alembic.ini                # Alembic 設定
├── alembic/                   # Alembic migrations
│
├── docker-compose.yaml        # 開發/建置用 (含 build 指令)
├── docker-compose.dev.yaml    # 開發環境精簡版 (只啟動 Redis)
├── docker-compose.prod.yaml   # 正式環境 (全容器化)
│
├── app/                       # 後端程式碼
│   ├── .env                   # 後端應用程式環境變數 (DB, Auth, Redis)
│   └── Dockerfile             # 後端映像定義
│
└── frontend/                  # 前端程式碼
    ├── .env.development       # 前端開發環境變數
    ├── .env.production        # 前端正式環境變數
    └── Dockerfile             # 前端映像定義 (Node build + Nginx)
```

---

## Dockerfile 設計

### 後端 (`app/Dockerfile`)

```dockerfile
FROM python:3.11-slim
WORKDIR /project

# 安裝系統依賴與 uv
RUN apt-get update && apt-get install -y gcc python3-dev libpq-dev curl \
    && pip install uv

# 將虛擬環境建在 /opt/venv (避免 COPY . . 時被本機的 .venv 覆蓋)
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"

# 先複製套件定義，利用 Docker 快取層
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 複製程式碼
COPY . .

# 環境變數
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/project
ENV PYTHONUNBUFFERED=1
```

**關鍵設計決策**:
1. **`UV_PROJECT_ENVIRONMENT="/opt/venv"`**: 避免 `COPY . .` 時本機 `.venv` 覆蓋 Docker 內的虛擬環境
2. **Build context 為專案根目錄** (`context: .`)：因為 `pyproject.toml` 和 `uv.lock` 位於根目錄
3. **`dockerfile: app/Dockerfile`**: 告訴 Docker 去 app 資料夾找 Dockerfile

### 前端 (`frontend/Dockerfile`)

```dockerfile
# 多階段建置
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# 最終映像
FROM nginx:alpine
COPY ./nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/dist /usr/share/nginx/html
```

**注意**:
- `npm run build` 使用 `.env.production`，WebSocket URL 會指向正式環境 (`boss-timer.jaao.tw`)
- Node base image 固定用 `node:22-alpine`（Node 18 已於 2025/04 EOL）；`nginx:alpine` 使用 floating tag，每次 `--no-cache` build 即可取得最新安全版本

---

## Docker Compose 配置

### 開發環境 (`docker-compose.dev.yaml`)

只啟動 Redis，後端和前端在本機執行：

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: boss_redis_dev
    ports:
      - "6379:6379"
```

### 建置與測試 (`docker-compose.yaml`)

完整的開發建置環境，包含所有服務：

| 服務 | 說明 | Port |
|---|---|---|
| `boss_service` | FastAPI 後端 | 1254 |
| `boss_timer_nginx` | 前端 Nginx | 2255 |
| `redis` | Redis (Celery Broker) | 6381 |
| `celery_worker_fast` | 一般任務 Worker (concurrency=4) | — |
| `celery_worker_discord` | Discord 推播 Worker (concurrency=1) | — |

### 正式環境 (`docker-compose.prod.yaml`)

在建置版本基礎上增加：

| 服務 | 額外設定 |
|---|---|
| `db` | PostgreSQL, port 4521, 持久化 volume |
| `boss_service` | healthcheck, env_file, 網路隔離 |
| `boss_timer_nginx` | depends_on service_healthy, 掛載 nginx.conf |
| `redis` | 網路隔離 |
| `celery_worker_fast` | depends_on redis + db |
| `celery_worker_discord` | depends_on redis + db |

**所有服務指定 `platform: linux/arm64`**，確保拉取 ARM 映像。

---

## 環境變數管理

### 根目錄 `.env` (Docker Compose 專用)
```
REMOTE_REGISTRY_IP=harbor.jaao.tw
BACKEND_VERSION=2.6.1
FRONTEND_VERSION=2.4.1
```

### `app/.env` (後端應用程式)
```
DB_USER=...
DB_PASSWORD=...
DB_HOST=...
DB_PORT=4521
DB_NAME=boss_tracker
SECRET_KEY=...
ENV=development
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

### Docker 容器內的 `.env` 掛載
- `docker-compose.yaml`: `./app/.env:/project/.env` (掛載到 WORKDIR)
- `docker-compose.prod.yaml`: 使用 `env_file: - .env` 讀取根目錄 `.env`
- `REDIS_URL` 透過 `environment` 直接注入 (`redis://redis:6379/0`)

---

## 開發工作流程

### 本機開發 (推薦)

使用混合模式：Redis 跑 Docker，其餘跑本機。

**終端機 1 — Redis**:
```bash
docker compose -f docker-compose.dev.yaml up -d
```

**終端機 2 — 後端 API**:
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 1254 \
  --ssl-keyfile=frontend/vite-key.pem --ssl-certfile=frontend/vite.pem
```

**終端機 3 — Celery Worker**:
```bash
uv run celery -A app.celery_app worker -Q celery,discord_queue --concurrency=2 --loglevel=info
```

**終端機 4 — 前端**:
```bash
cd frontend && npm run dev
```

### 資料庫遷移
```bash
# 在專案根目錄執行 (不是 app/ 裡面！)
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```

---

## 部署流程

### 1. 建置映像
```bash
# 使用 docker-compose.yaml 內的 build 定義
docker compose build
```

### 2. 推送至 Registry
```bash
docker push harbor.jaao.tw/boss_service/boss_service:${BACKEND_VERSION}
docker push harbor.jaao.tw/boss_service/boss_timer_nginx:${FRONTEND_VERSION}
```

### 3. 在正式機啟動
```bash
docker compose -f docker-compose.prod.yaml up -d
```

### 4. 資料庫遷移 (正式機)
```bash
# 在正式機進入 boss_service 容器執行
docker compose -f docker-compose.prod.yaml exec boss_service \
  alembic upgrade head
```

---

## .dockerignore (根目錄)

```
app/db/
db-data/
db-init/
.venv/
.git/
__pycache__/
*.pyc
frontend/node_modules/
frontend/dist/
.env
.env.*
```

**用途**: 防止 Docker build context 傳輸過大檔案 (如 `.venv/`, `.git/`, `node_modules/`)，同時避免 `db-data/` 的 permission denied 錯誤。

---

## 重要注意事項

1. **Alembic 必須在專案根目錄執行**，不能在 `app/` 裡面，否則會報 `No 'script_location' key found`
2. **Docker build context 是專案根目錄 (`.`)**，而非 `app/`，因為 `pyproject.toml` 和 `uv.lock` 在根目錄
3. **前端 Docker Image 的 WebSocket URL 是編譯時決定的**：使用 `.env.production` 中的 `VITE_WS_URL`，部署後無法更改
4. **Redis port mapping**: 開發用 6379 (標準)，Docker Compose 用 6381 (避免與系統其他 Redis 衝突)
5. **Celery Worker 不建議用 root 執行**，Docker 中建議在 Dockerfile 加入非 root 使用者
