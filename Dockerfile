# build stage
FROM node:lts-alpine AS build-stage
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# production stage
FROM nginx:latest AS prod

# 複製構建後的檔案
COPY --from=build-stage /app/dist /usr/share/nginx/html
#COPY ./googlea3a83c53d0b01668.html /usr/share/nginx/html
# 複製 nginx 配置
COPY nginx/nginx_conf/nginx.conf /etc/nginx/nginx.conf
RUN mkdir -p /etc/nginx/conf.d
RUN chmod 644 /etc/nginx/nginx.conf
RUN rm /etc/nginx/conf.d/default.conf

EXPOSE 80