#!/usr/bin/env bash
set -euo pipefail

NEW_TAG="${1:?需要傳入 image tag}"
COMPOSE_DIR=~/boss-tracker
source "$(dirname "$0")/lib.sh"

cd "$COMPOSE_DIR"
require_tools
acquire_deploy_lock

# 1. 判斷目前 active slot
CURRENT=$(active_slot)
NEXT=$(other_slot "$CURRENT")
NEXT_UPPER=$(echo "$NEXT" | tr '[:lower:]' '[:upper:]')

echo "▶ 目前: $CURRENT → 部署到: $NEXT (tag: $NEW_TAG)"

# 2. 更新 next slot tag
PREV_NEXT_TAG=$(grep "^${NEXT_UPPER}_TAG=" .env | cut -d= -f2)
sed -i "s/^${NEXT_UPPER}_TAG=.*/${NEXT_UPPER}_TAG=${NEW_TAG}/" .env

# 切換完成前任何一步失敗：還原 next slot 的 tag 並停掉它。
# 否則 .env 會留著沒通過檢查的版本，之後按回滾會切到這個壞掉的版本。
SWITCHED=0
restore_next_slot() {
  [ "$SWITCHED" = 1 ] && return
  echo "▶ 部署未完成，還原 ${NEXT_UPPER}_TAG=${PREV_NEXT_TAG} 並停止 ${NEXT}..."
  sed -i "s/^${NEXT_UPPER}_TAG=.*/${NEXT_UPPER}_TAG=${PREV_NEXT_TAG}/" .env
  docker compose stop "boss_service_${NEXT}" "boss_timer_nginx_${NEXT}" || true
}
trap restore_next_slot EXIT

# 3. Pull 新 image
docker compose pull "boss_service_${NEXT}" "boss_timer_nginx_${NEXT}"

# 4. 跑 migration（只跑一次）
echo "▶ 執行 DB migration..."
docker compose run --rm "boss_service_${NEXT}" alembic upgrade head

# 5. 起 next slot
echo "▶ 啟動 ${NEXT} 容器..."
docker compose up -d --no-deps "boss_service_${NEXT}" "boss_timer_nginx_${NEXT}"

# 6. 等 healthcheck
wait_healthy "$NEXT" || { echo "❌ 健康檢查逾時，放棄部署"; exit 1; }

# 7. 切換 Traefik 流量（改檔案，Traefik 自動偵測），並停掉舊 slot
switch_and_stop "$NEXT" "$CURRENT"
SWITCHED=1
record_switch deploy "$NEW_TAG"

# 8. 更新 Celery worker
set_active_tag "$NEW_TAG"

echo "✅ 完成！流量已切到 ${NEXT} (${NEW_TAG})，舊 slot ${CURRENT} 已停止"
echo "   回滾指令：${COMPOSE_DIR}/rollback.sh"
