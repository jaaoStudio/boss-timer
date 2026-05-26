# Frontend Dockerfile (frontend/Dockerfile)
FROM node:22-alpine AS builder

# 設置工作目錄
WORKDIR /app

# 複製 package.json 和 package-lock.json
COPY package*.json ./

# 安裝依賴
RUN npm ci

# 複製源代碼
COPY . .

ARG VITE_GTM_ID
ARG VITE_ANALYTICS_ID
ARG VITE_GOOGLE_CLIENT_ID
ARG VITE_WS_URL
ARG VITE_APP_BASE_URL
ARG VITE_BASE_PUBLIC_PATH
ARG VITE_APP_TITLE
ARG VITE_CLARITY_ID

ENV VITE_GTM_ID=$VITE_GTM_ID
ENV VITE_ANALYTICS_ID=$VITE_ANALYTICS_ID
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
ENV VITE_WS_URL=$VITE_WS_URL
ENV VITE_APP_BASE_URL=$VITE_APP_BASE_URL
ENV VITE_BASE_PUBLIC_PATH=$VITE_BASE_PUBLIC_PATH
ENV VITE_APP_TITLE=$VITE_APP_TITLE
ENV VITE_CLARITY_ID=$VITE_CLARITY_ID

# 構建應用 (Vue.js 項目通常使用 npm run build)
RUN npm run build

# Production stage
FROM nginx:alpine

# 複製自定義 nginx 配置
COPY ./nginx/nginx.conf /etc/nginx/nginx.conf

# 複製構建產物到 nginx 服務目錄
# Vue.js 項目構建產物通常在 dist 目錄
COPY --from=builder /app/dist /usr/share/nginx/html


# 暴露端口
EXPOSE 80

# 啟動 nginx
CMD ["nginx", "-g", "daemon off;"]