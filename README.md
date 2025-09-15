# Artale BOSS Timer

一個為楓之谷世界 (Artale) 設計的即時 Boss 計時器，幫助玩家和團隊高效追蹤 Boss 的重生狀態。

[Live Demo](https://boss-timer.jaao.tw/)

![專案截圖](boss-timer.jaao.tw_.png)

## ✨ 主要功能

- **即時狀態追蹤**: 即時顯示 Boss 的存活、死亡和即將重生狀態。
- **多人協作房間**: 支援建立多個獨立的房間，方便不同隊伍或社群使用。
- **WebSocket 即時更新**: 所有狀態變更都會透過 WebSocket 立即同步給房間內的所有使用者。
- **Google 帳號登入**: 透過 Google OAuth 進行安全快速的身份驗證。
- **多國語言**: 支援繁體中文和英文介面。
- **響應式設計**: 在桌面和行動裝置上都有良好的使用體驗。
- **系統維護模式**: 可由管理員開啟，方便進行系統更新與維護。

## 🛠️ 技術棧

| 類別 | 技術 |
| :--- | :--- |
| **後端** | Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL, Uvicorn, WebSockets |
| **前端** | Vue.js 3, Vite, Pinia, Vue Router, Tailwind CSS, Element Plus |
| **部署** | Docker, Docker Compose, Nginx |

## 🚀 快速開始 (本地開發)

本指南將引導您在本地開發環境中，完整地設定並執行此專案。

### 第 1 步：設定環境變數

專案的設定被拆分成三個獨立的 `.env` 檔案。請依照以下步驟，從範本建立您自己的設定檔。

#### a) 資料庫初始化設定

此設定檔用於**首次建立**資料庫容器時，設定 PostgreSQL 的超級使用者。

```bash
# 進入資料庫設定目錄
cd app/db

# 從範本複製設定檔
cp .env.example .env
```
> `app/db/.env` 內的帳號密碼是資料庫容器的最高權限帳密，通常在本地開發外不需要修改。

#### b) 後端應用程式設定

此設定檔告知 FastAPI 後端應用程式如何**連線到資料庫**，以及 Google OAuth 和 JWT 的金鑰。

```bash
# 回到專案根目錄
cd ../..

# 進入後端應用程式目錄
cd app

# 從範本複製設定檔
cp .env.example .env
```
**請務必編輯 `app/.env`**，將 `POSTGRES_SERVER` 改為 `localhost` (如果資料庫在本機)，並填入您自己的 `SECRET_KEY` 和 `GOOGLE_CLIENT_ID`。

#### c) 前端應用程式設定

此設定檔告知 Vue.js 前端應用程式後端 API 的位址和 Google 相關的 ID。

```bash
# 回到專案根目錄
cd ..

# 進入前端目錄
cd frontend

# 從範本複製設定檔
cp .env.example .env
```
編輯 `frontend/.env` 並填入您自己的 Google 服務 ID。

### 第 2 步：啟動服務與資料庫遷移

完成所有設定後，請回到專案根目錄，並依照以下順序啟動服務。

#### a) 啟動資料庫服務

```bash
# 進入資料庫目錄
cd app/db

# 在背景啟動資料庫容器
docker-compose up -d
```

#### b) 執行資料庫遷移

資料庫啟動後，我們需要使用 Alembic 工具建立所需的資料表。

```bash
# 回到專案根目錄
cd ../..

# 執行遷移指令 (此指令會建立/更新資料庫中的資料表)
alembic upgrade head
```
> **注意**: 您需要在本地端安裝 `alembic` 和專案所需的 Python 套件才能執行此指令。或者，您也可以進入 `boss_service` 容器中執行此指令。

#### c) 啟動主應用程式

最後，建置並啟動後端和前端服務。

```bash
# 確認您在專案根目錄

# 使用您的參數建置並啟動服務
REMOTE_REGISTRY_IP=harbor.jaao.tw \
BACKEND_VERSION=2.4.3 \
FRONTEND_VERSION=2.2.5 \
docker-compose up -d --build
```

### 第 3 步：瀏覽網站

所有服務都成功啟動後，您可以在瀏覽器中開啟 `http://localhost:2255` 來查看網站。


## 📁 專案結構

```
.
├── app/            # FastAPI 後端應用程式
│   ├── database/   # 資料庫模型與設定
│   ├── routers/    # API 路由
│   ├── schemas/    # Pydantic 資料模型
│   ├── services/   # 業務邏輯服務
│   └── main.py     # 應用程式進入點
├── frontend/       # Vue.js 前端應用程式
│   ├── src/
│   │   ├── components/ # Vue 組件
│   │   ├── stores/     # Pinia 狀態管理
│   │   ├── views/      # 頁面視圖
│   │   └── main.ts     # 前端進入點
│   └── vite.config.ts  # Vite 設定
├── docker-compose.yaml # Docker Compose 設定
└── alembic/        # 資料庫遷移工具
```

## 🤝 貢獻

歡迎任何形式的貢獻！如果您有任何建議或發現了 Bug，請隨時提出 Issue 或發送 Pull Request。

## 📄 授權

本專案採用 [MIT License](LICENSE)。
