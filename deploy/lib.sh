#!/usr/bin/env bash
# deploy.sh / rollback.sh 共用的 blue/green 切換步驟。由兩支腳本 source，需在 $COMPOSE_DIR 下執行。

TRAEFIK_DYNAMIC="${TRAEFIK_DYNAMIC:-/opt/traefik/dynamic/boss-timer.yml}"
TRAEFIK_API="${TRAEFIK_API:-http://127.0.0.1:8081}"   # 與 sync_cloudflare_ips.py 相同的 base URL
TRAEFIK_ROUTER=boss-frontend@file
SWITCH_GRACE_SECONDS=3
# 確認 slot 可用的路徑：經 nginx 轉給同 slot 的後端，前後端都正常才算通
SLOT_PROBE_PATH=/api/health

# slot 對應的 Traefik service（定義在 /opt/traefik/dynamic/boss-services.yml）
frontend_service() {
  echo "boss-frontend-$1@file"
}

# 切換流程用到的工具。jq / curl 讀 Traefik API，缺少時確認一定失敗，先明確擋下
require_tools() {
  local tool
  for tool in docker curl jq flock; do
    command -v "$tool" >/dev/null || { echo "❌ 正式機缺少 ${tool}，無法執行部署 / 回滾"; exit 1; }
  done
}

# 記錄最後一次成功的切換（deploy / rollback），回滾用來擋重複執行
record_switch() {
  echo "$1 $2 $(date -Is)" > "${COMPOSE_DIR}/.last_switch"
}

last_switch_kind() {
  cut -d' ' -f1 "${COMPOSE_DIR}/.last_switch" 2>/dev/null || true
}

# 同一時間只允許一個部署 / 回滾：兩邊同時跑會讀到同一個 active slot、互相重建同一組容器。
# CI 的 deploy.yml 另以 concurrency 讓部署排隊；回滾與手動執行靠這個鎖互斥。
# 等待上限需小於 ssh-action 的 command_timeout（20 分鐘），逾時才能乾淨地以失敗結束。鎖在腳本結束時自動釋放。
acquire_deploy_lock() {
  exec 9>"${COMPOSE_DIR}/.deploy.lock"
  echo "▶ 取得部署鎖..."
  flock -w 600 9 || { echo "❌ 10 分鐘內等不到部署鎖（有其他部署 / 回滾正在執行），放棄"; exit 1; }
}

# 每 interval 秒執行一次指令，成功就回傳 0，最多 tries 次
retry() {
  local tries="$1" interval="$2"
  shift 2
  for _ in $(seq "$tries"); do
    "$@" && return 0
    sleep "$interval"
  done
  return 1
}

# 目前接流量的 slot（blue / green）
active_slot() {
  local slot
  slot=$(sed -n 's/.*service: boss-frontend-\(blue\|green\)@file.*/\1/p' "$TRAEFIK_DYNAMIC" | head -n1)
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

# 從 Traefik 容器內連得到 slot（與 Traefik 轉送走同一個網路與 DNS），容器內重試約 15 秒。
# boss-services.yml 刻意不設 healthCheck：每個 slot 只有一台，健康檢查無從容錯，
# 一次回應慢就會讓整站回 503，所以由這裡在切換前後主動確認
traefik_can_reach() {
  docker exec traefik sh -c \
    "for _ in 1 2 3 4 5; do wget -q -T 3 -O /dev/null http://boss_timer_nginx_$1:80${SLOT_PROBE_PATH} && exit 0; sleep 2; done; exit 1" \
    2>/dev/null
}

# Traefik 已重新載入設定，路由正在使用 slot 的 service
traefik_routed_to() {
  curl -fsS --max-time 2 "${TRAEFIK_API}/api/http/services/$(frontend_service "$1")" 2>/dev/null \
    | jq -e --arg router "$TRAEFIK_ROUTER" '(.usedBy // [] | index($router)) != null' >/dev/null
}

point_traefik_to() {
  sed -i "s/service: boss-frontend-.*/service: $(frontend_service "$1")/" "$TRAEFIK_DYNAMIC"
}

# 把流量切到 to_slot，再停掉 from_slot（見 docs/adr/0005-deploy-stops-old-slot.md）
# 房間訂閱只存在單一後端容器的記憶體，舊 slot 若繼續存活，既有的 WebSocket 連線會留在舊容器，
# 同一房間被拆成兩群。停掉後前端會自動重連到新 slot 並重新取得房間狀態。
# 確認 Traefik 真的在用新 slot 之後才停舊 slot；任何一步確認不到就還原路由、保留舊 slot。
switch_and_stop() {
  local to_slot="$1" from_slot="$2"
  echo "▶ 確認 Traefik 連得到 ${to_slot}（${SLOT_PROBE_PATH}）..."
  traefik_can_reach "$to_slot" || { echo "❌ Traefik 連不到 boss_timer_nginx_${to_slot}${SLOT_PROBE_PATH}，放棄切換（流量仍在 ${from_slot}）"; exit 1; }

  echo "▶ 切換流量到 ${to_slot}..."
  point_traefik_to "$to_slot"
  # 等 Traefik 重新載入檔案（每次最多約 4 秒，共約 2 分鐘），再確認一次新 slot 仍可用
  if ! retry 30 2 traefik_routed_to "$to_slot" || ! traefik_can_reach "$to_slot"; then
    echo "❌ Traefik 未改用 ${to_slot} 或 ${to_slot} 已無法使用，還原路由到 ${from_slot}"
    point_traefik_to "$from_slot"
    retry 15 2 traefik_routed_to "$from_slot" || echo "⚠️ Traefik 尚未確認改回 ${from_slot}，請手動檢查"
    # 切換期間可能已有 WebSocket 連進新 slot；停掉讓它們重連回舊 slot，避免同一房間分成兩群（ADR-0005）
    echo "▶ 停止 ${to_slot}..."
    docker compose stop "boss_service_${to_slot}" "boss_timer_nginx_${to_slot}"
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
