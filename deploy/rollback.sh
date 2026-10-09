#!/usr/bin/env bash
# rollback.sh
# 部署後舊 slot 會被停止（見 docs/adr/0005-deploy-stops-old-slot.md），
# 回滾需先重新啟動舊 slot、等健康檢查通過，再切回流量並停掉目前的 slot。
set -euo pipefail
# 用法：rollback.sh [--force]
# 上一次切換已經是回滾時預設拒絕執行：連按兩次回滾，第二次會把第一次切回去。要再切回去請重新部署，或加 --force
FORCE="${1:-}"
COMPOSE_DIR=~/boss-tracker
source "$(dirname "$0")/lib.sh"
cd "$COMPOSE_DIR"
require_tools
acquire_deploy_lock

if [ "$(last_switch_kind)" = rollback ] && [ "$FORCE" != "--force" ]; then
  echo "❌ 上一次切換已經是回滾（$(cat .last_switch)），不再切換。要切回去請重新部署，或執行 rollback.sh --force"
  exit 1
fi

CURRENT=$(active_slot)
PREV=$(other_slot "$CURRENT")
PREV_UPPER=$(echo "$PREV" | tr '[:lower:]' '[:upper:]')
PREV_TAG=$(grep "^${PREV_UPPER}_TAG=" .env | cut -d= -f2)

# 1. 重新啟動舊 slot（沿用 .env 中舊 slot 的 tag）
echo "▶ 啟動 ${PREV} (tag: ${PREV_TAG})..."
docker compose up -d --no-deps "boss_service_${PREV}" "boss_timer_nginx_${PREV}"

# 2. 等 healthcheck
wait_healthy "$PREV" || { echo "❌ 健康檢查逾時，放棄回滾（流量仍在 ${CURRENT}）"; exit 1; }

# 3. 切回流量並停掉目前的 slot
switch_and_stop "$PREV" "$CURRENT"
record_switch rollback "$PREV_TAG"

# 4. Celery worker 一併回到舊版
set_active_tag "$PREV_TAG"

echo "✅ 已切回 ${PREV} (${PREV_TAG})"
