#!/usr/bin/env bash
# rollback.sh
set -euo pipefail
TRAEFIK_DYNAMIC=/opt/traefik/dynamic/boss-timer.yml
COMPOSE_DIR=~/boss-tracker
cd "$COMPOSE_DIR"

CURRENT=$(grep "service: boss-frontend-" "$TRAEFIK_DYNAMIC" | grep -o 'blue\|green')
if [ "$CURRENT" = "blue" ]; then PREV=green; else PREV=blue; fi

echo "▶ 切回 $PREV..."
sed -i "s/service: boss-frontend-.*/service: boss-frontend-${PREV}@docker/" "$TRAEFIK_DYNAMIC"
echo "✅ 已切回 $PREV"
