#!/usr/bin/env bash
# deploy.sh / rollback.sh 共用的 blue/green 切換步驟。由兩支腳本 source，需在 $COMPOSE_DIR 下執行。

TRAEFIK_DYNAMIC=/opt/traefik/dynamic/boss-timer.yml
SWITCH_GRACE_SECONDS=10

# 目前接流量的 slot（blue / green）
active_slot() {
  grep "service: boss-frontend-" "$TRAEFIK_DYNAMIC" | grep -o 'blue\|green'
}

other_slot() {
  if [ "$1" = "blue" ]; then echo green; else echo blue; fi
}

# 等 slot 的 nginx healthcheck 通過（最多 2 分鐘）；逾時回傳 1
wait_healthy() {
  local slot="$1" status
  echo "▶ 等待 ${slot} 健康檢查（最多 2 分鐘）..."
  for i in $(seq 1 12); do
    status=$(docker inspect "boss_timer_nginx_${slot}" \
      --format='{{.State.Health.Status}}' 2>/dev/null || echo "starting")
    echo "  [$i/12] $status"
    [ "$status" = "healthy" ] && return 0
    sleep 10
  done
  return 1
}

# 把流量切到 to_slot，再停掉 from_slot（見 docs/adr/0005-deploy-stops-old-slot.md）
# 房間訂閱只存在單一後端容器的記憶體，舊 slot 若繼續存活，既有的 WebSocket 連線會留在舊容器，
# 同一房間被拆成兩群。停掉後前端會自動重連到新 slot 並重新取得房間狀態。
# 先等 Traefik 載入新設定，避免新連線在切換完成前打到即將停止的容器。
switch_and_stop() {
  local to_slot="$1" from_slot="$2"
  echo "▶ 切換流量到 ${to_slot}..."
  sed -i "s/service: boss-frontend-.*/service: boss-frontend-${to_slot}@file/" "$TRAEFIK_DYNAMIC"
  echo "▶ 等待 Traefik 套用新路由（${SWITCH_GRACE_SECONDS} 秒）..."
  sleep "$SWITCH_GRACE_SECONDS"
  echo "▶ 停止 ${from_slot}..."
  docker compose stop "boss_service_${from_slot}" "boss_timer_nginx_${from_slot}"
}

# Celery worker 不分 blue/green，跟著目前生效的 tag 重啟
set_active_tag() {
  sed -i "s/^ACTIVE_TAG=.*/ACTIVE_TAG=$1/" .env
  docker compose up -d --no-deps celery_worker_fast celery_worker_discord
}
