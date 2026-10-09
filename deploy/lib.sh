#!/usr/bin/env bash
# deploy.sh / rollback.sh 共用的 blue/green 切換步驟。由兩支腳本 source，需在 $COMPOSE_DIR 下執行。

TRAEFIK_DYNAMIC=/opt/traefik/dynamic/boss-timer.yml
TRAEFIK_API=http://127.0.0.1:8081/api/http
SWITCH_GRACE_SECONDS=10

# 同一時間只允許一個部署 / 回滾。CI 已用 workflow concurrency 排隊，這裡擋手動執行時與 CI 撞在一起：
# 兩邊同時部署會讀到同一個 active slot、部署到同一個 slot，互相重建容器。
# 鎖在腳本結束（fd 9 關閉）時自動釋放。
acquire_deploy_lock() {
  exec 9>"${COMPOSE_DIR}/.deploy.lock"
  echo "▶ 取得部署鎖..."
  flock -w 1800 9 || { echo "❌ 30 分鐘內等不到部署鎖（有其他部署 / 回滾正在執行），放棄"; exit 1; }
}

# 目前接流量的 slot（blue / green）
active_slot() {
  local slot
  slot=$(grep -m1 "service: boss-frontend-" "$TRAEFIK_DYNAMIC" | grep -o -m1 'blue\|green' || true)
  [ -n "$slot" ] || { echo "❌ 無法從 ${TRAEFIK_DYNAMIC} 判斷目前的 slot" >&2; return 1; }
  echo "$slot"
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

# 讀 Traefik API 的 JSON 欄位；$1 = API 路徑，$2 = Python 運算式（d 為解析後的 JSON）。失敗時輸出空字串
traefik_json() {
  curl -fsS --max-time 5 "${TRAEFIK_API}/$1" 2>/dev/null \
    | python3 -I -c "import json, sys; d = json.load(sys.stdin); print($2)" 2>/dev/null || true
}

# 從 Traefik 容器內連得到 slot 的 nginx（與 Traefik 轉送走同一個網路與 DNS），最多 30 秒
# 未被路由使用的 service 不會做健康檢查，切換前只能這樣確認
wait_traefik_can_reach() {
  local slot="$1"
  for i in $(seq 1 15); do
    docker exec traefik wget -q -T 3 -O /dev/null "http://boss_timer_nginx_${slot}:80/" 2>/dev/null && return 0
    sleep 2
  done
  return 1
}

# 路由已指向 slot，且 Traefik 對它的健康檢查回報 UP，最多 60 秒
wait_traefik_serving() {
  local slot="$1" service status
  for i in $(seq 1 30); do
    service=$(traefik_json "routers/boss-frontend@file" 'd.get("service")')
    status=$(traefik_json "services/boss-frontend-${slot}@file" '",".join((d.get("serverStatus") or {}).values())')
    [ "$service" = "boss-frontend-${slot}@file" ] && [ "$status" = "UP" ] && return 0
    sleep 2
  done
  echo "  Traefik 路由：${service:-無法取得}；boss-frontend-${slot}@file 狀態：${status:-無法取得}"
  return 1
}

point_traefik_to() {
  sed -i "s/service: boss-frontend-.*/service: boss-frontend-$1@file/" "$TRAEFIK_DYNAMIC"
}

# 把流量切到 to_slot，再停掉 from_slot（見 docs/adr/0005-deploy-stops-old-slot.md）
# 房間訂閱只存在單一後端容器的記憶體，舊 slot 若繼續存活，既有的 WebSocket 連線會留在舊容器，
# 同一房間被拆成兩群。停掉後前端會自動重連到新 slot 並重新取得房間狀態。
# 確認 Traefik 真的在用新 slot 之後才停舊 slot；任何一步確認不到就還原路由、保留舊 slot。
switch_and_stop() {
  local to_slot="$1" from_slot="$2"
  echo "▶ 確認 Traefik 連得到 ${to_slot}..."
  wait_traefik_can_reach "$to_slot" || { echo "❌ Traefik 連不到 boss_timer_nginx_${to_slot}，放棄切換（流量仍在 ${from_slot}）"; exit 1; }

  echo "▶ 切換流量到 ${to_slot}..."
  point_traefik_to "$to_slot"
  if ! wait_traefik_serving "$to_slot"; then
    echo "❌ Traefik 未改用 ${to_slot}，還原路由（流量仍在 ${from_slot}）"
    point_traefik_to "$from_slot"
    exit 1
  fi

  echo "▶ Traefik 已改用 ${to_slot}，等待 ${SWITCH_GRACE_SECONDS} 秒讓 ${from_slot} 完成進行中的請求..."
  sleep "$SWITCH_GRACE_SECONDS"
  echo "▶ 停止 ${from_slot}..."
  docker compose stop "boss_service_${from_slot}" "boss_timer_nginx_${from_slot}"
}

# Celery worker 不分 blue/green，跟著目前生效的 tag 重啟
set_active_tag() {
  sed -i "s/^ACTIVE_TAG=.*/ACTIVE_TAG=$1/" .env
  docker compose up -d --no-deps celery_worker_fast celery_worker_discord
}
