# Frontend Dockerfile (frontend/Dockerfile)
FROM node:18-alpine AS builder

# 設置工作目錄
WORKDIR /app

# 複製 package.json 和 package-lock.json
COPY package*.json ./

# 安裝依賴
RUN npm ci

# 複製源代碼
COPY . .

# 構建應用 (Vue.js 項目通常使用 npm run build)
RUN npm run build

# Production stage
FROM nginx:alpine

# 複製自定義 nginx 配置
COPY ./nginx/nginx.conf /etc/nginx/nginx.conf

# 複製構建產物到 nginx 服務目錄
# Vue.js 項目構建產物通常在 dist 目錄
COPY --from=builder /app/dist /usr/share/nginx/html

# 複製 public 目錄下的內容 (例如維護頁面)
COPY ./public/ /usr/share/nginx/html/

# 複製 ads.txt
COPY ./ads.txt /usr/share/nginx/html/ads.txt


# 暴露端口
EXPOSE 80

# 啟動 nginx
CMD ["nginx", "-g", "daemon off;"]