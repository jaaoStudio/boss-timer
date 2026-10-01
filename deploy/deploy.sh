#!/usr/bin/env bash
set -euo pipefail

NEW_TAG="${1:?需要傳入 image tag}"
COMPOSE_DIR=~/boss-tracker
TRAEFIK_DYNAMIC=/opt/traefik/dynamic/boss-timer.yml

cd "$COMPOSE_DIR"

# 1. 判斷目前 active slot
CURRENT=$(grep "service: boss-frontend-" "$TRAEFIK_DYNAMIC" | grep -o 'blue\|green')
if [ "$CURRENT" = "blue" ]; then NEXT=green; else NEXT=blue; fi
NEXT_UPPER=$(echo "$NEXT" | tr '[:lower:]' '[:upper:]')

echo "▶ 目前: $CURRENT → 部署到: $NEXT (tag: $NEW_TAG)"

# 2. 更新 next slot tag
sed -i "s/^${NEXT_UPPER}_TAG=.*/${NEXT_UPPER}_TAG=${NEW_TAG}/" .env

# 3. Pull 新 image
docker compose pull "boss_service_${NEXT}" "boss_timer_nginx_${NEXT}"

# 4. 跑 migration（只跑一次）
echo "▶ 執行 DB migration..."
docker compose run --rm "boss_service_${NEXT}" alembic upgrade head

# 5. 起 next slot
echo "▶ 啟動 ${NEXT} 容器..."
docker compose up -d --no-deps "boss_service_${NEXT}" "boss_timer_nginx_${NEXT}"

# 6. 等 healthcheck
echo "▶ 等待健康檢查（最多 2 分鐘）..."
for i in $(seq 1 12); do
  STATUS=$(docker inspect "boss_timer_nginx_${NEXT}" \
    --format='{{.State.Health.Status}}' 2>/dev/null || echo "starting")
  echo "  [$i/12] $STATUS"
  [ "$STATUS" = "healthy" ] && break
  [ $i -eq 12 ] && { echo "❌ 健康檢查逾時，放棄部署"; exit 1; }
  sleep 10
done

# 7. 切換 Traefik 流量（改檔案，Traefik 自動偵測）
echo "▶ 切換流量到 ${NEXT}..."
sed -i "s/service: boss-frontend-.*/service: boss-frontend-${NEXT}@docker/" "$TRAEFIK_DYNAMIC"

# 8. 更新 Celery worker
sed -i "s/^ACTIVE_TAG=.*/ACTIVE_TAG=${NEW_TAG}/" .env
docker compose up -d --no-deps celery_worker_fast celery_worker_discord

echo "✅ 完成！流量已切到 ${NEXT} (${NEW_TAG})"
echo "   回滾指令：sed -i 's/boss-frontend-${NEXT}/boss-frontend-${CURRENT}/' ${TRAEFIK_DYNAMIC}"
