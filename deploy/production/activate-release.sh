#!/bin/sh
set -eu

DEPLOY_ROOT=/mnt/CUHA_BOT
RELEASE_DIR=${1:-}

case "$RELEASE_DIR" in
  "$DEPLOY_ROOT"/releases/*) ;;
  *) echo "release must be below $DEPLOY_ROOT/releases" >&2; exit 2 ;;
esac
test -d "$RELEASE_DIR"
test -f "$DEPLOY_ROOT/.env"

PREVIOUS=$(readlink -f "$DEPLOY_ROOT/current" 2>/dev/null || true)
if [ -z "$PREVIOUS" ] && [ -f "$DEPLOY_ROOT/docker-compose.yml" ]; then
  PREVIOUS=$DEPLOY_ROOT
fi
ln -sfn "$DEPLOY_ROOT/.env" "$RELEASE_DIR/.env"
chmod 600 "$DEPLOY_ROOT/.env"

rollback() {
  trap - EXIT INT TERM HUP
  echo "release activation failed; rolling back" >&2
  if [ -n "$PREVIOUS" ] && [ -d "$PREVIOUS" ]; then
    cd "$PREVIOUS"
    docker compose up -d --build
    ln -sfn "$PREVIOUS" "$DEPLOY_ROOT/current"
  fi
}
on_exit() {
  status=$?
  if [ "$status" -ne 0 ]; then rollback; fi
  exit "$status"
}
trap on_exit EXIT INT TERM HUP

cd "$RELEASE_DIR"
python scripts/migrate_roguelike_reward_system.py
python scripts/migrate_balance_v2.py
docker compose up -d --build

attempt=0
while :; do
  status=$(docker inspect --format '{{.State.Health.Status}}' cuhabot 2>/dev/null || true)
  case "$status" in
    healthy) break ;;
    unhealthy) exit 1 ;;
  esac
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 36 ]; then
    docker compose logs --tail=150 cuhabot >&2 || true
    exit 1
  fi
  sleep 5
done

ln -sfn "$RELEASE_DIR" "$DEPLOY_ROOT/current"
trap - EXIT INT TERM HUP
echo "Production release activated: $(basename "$RELEASE_DIR")"
