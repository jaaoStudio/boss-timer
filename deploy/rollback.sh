#!/usr/bin/env bash
# rollback.sh
# 部署後舊 slot 會被停止（見 docs/adr/0005-deploy-stops-old-slot.md），
# 回滾需先重新啟動舊 slot、等健康檢查通過，再切回流量並停掉目前的 slot。
set -euo pipefail
TRAEFIK_DYNAMIC=/opt/traefik/dynamic/boss-timer.yml
COMPOSE_DIR=~/boss-tracker
SWITCH_GRACE_SECONDS=10
cd "$COMPOSE_DIR"

CURRENT=$(grep "service: boss-frontend-" "$TRAEFIK_DYNAMIC" | grep -o 'blue\|green')
if [ "$CURRENT" = "blue" ]; then PREV=green; else PREV=blue; fi
PREV_UPPER=$(echo "$PREV" | tr '[:lower:]' '[:upper:]')
PREV_TAG=$(grep "^${PREV_UPPER}_TAG=" .env | cut -d= -f2)

# 1. 重新啟動舊 slot（沿用 .env 中舊 slot 的 tag）
echo "▶ 啟動 ${PREV} (tag: ${PREV_TAG})..."
docker compose up -d --no-deps "boss_service_${PREV}" "boss_timer_nginx_${PREV}"

# 2. 等 healthcheck
echo "▶ 等待健康檢查（最多 2 分鐘）..."
for i in $(seq 1 12); do
  STATUS=$(docker inspect "boss_timer_nginx_${PREV}" \
    --format='{{.State.Health.Status}}' 2>/dev/null || echo "starting")
  echo "  [$i/12] $STATUS"
  [ "$STATUS" = "healthy" ] && break
  [ $i -eq 12 ] && { echo "❌ 健康檢查逾時，放棄回滾（流量仍在 ${CURRENT}）"; exit 1; }
  sleep 10
done

# 3. 切回流量
echo "▶ 切回 ${PREV}..."
sed -i "s/service: boss-frontend-.*/service: boss-frontend-${PREV}@docker/" "$TRAEFIK_DYNAMIC"

# 4. 停掉目前的 slot，讓 WebSocket 連線重連到 ${PREV}
echo "▶ 等待 Traefik 套用新路由（${SWITCH_GRACE_SECONDS} 秒）..."
sleep "$SWITCH_GRACE_SECONDS"
echo "▶ 停止 ${CURRENT}..."
docker compose stop "boss_service_${CURRENT}" "boss_timer_nginx_${CURRENT}"

# 5. Celery worker 一併回到舊版
sed -i "s/^ACTIVE_TAG=.*/ACTIVE_TAG=${PREV_TAG}/" .env
docker compose up -d --no-deps celery_worker_fast celery_worker_discord

echo "✅ 已切回 ${PREV} (${PREV_TAG})"
