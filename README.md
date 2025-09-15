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

## 🚀 快速開始

您可以透過 Docker 快速在本地端啟動整個專案。

### 先決條件

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

### 安裝與啟動

1.  **Clone 專案**
    ```bash
    git clone https://your-repository-url.git
    cd boss-timing
    ```

2.  **設定環境變數**
    專案後端需要一些環境變數來設定資料庫連線、JWT 金鑰和 Google OAuth。請在專案根目錄建立一個 `.env` 檔案，並填入以下內容：

    ```env
    # .env

    # FastAPI 應用程式設定
    APP_VERSION="1.0.0"
    ALLOWED_ORIGINS="http://localhost:2255,http://your-frontend-domain.com"

    # 資料庫連線資訊
    POSTGRES_USER=your_db_user
    POSTGRES_PASSWORD=your_db_password
    POSTGRES_SERVER=db
    POSTGRES_PORT=5432
    POSTGRES_DB=boss_tracker_db

    # JWT 相關設定
    SECRET_KEY=your_super_secret_key_for_jwt
    ALGORITHM=HS256
    ACCESS_TOKEN_EXPIRE_MINUTES=30

    # Google OAuth 2.0 設定
    GOOGLE_CLIENT_ID="your-google-client-id.apps.googleusercontent.com"
    ```
    > **重要**: `SECRET_KEY` 務必更換為一個複雜且隨機的字串。

3.  **啟動服務**
    在專案根目錄執行以下指令來建置並啟動 Docker 容器：
    ```bash
    docker-compose up -d --build
    ```

4.  **瀏覽網站**
    啟動成功後，您可以在瀏覽器中開啟 `http://localhost:2255` 來查看網站。

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
