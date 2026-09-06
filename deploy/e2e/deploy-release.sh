#!/bin/sh
set -eu

DEPLOY_ROOT=/home/vulpo/CUHABot-e2e
RELEASE_DIR=${1:-}

case "$RELEASE_DIR" in
  "$DEPLOY_ROOT"/releases/*) ;;
  *) echo "release must be below $DEPLOY_ROOT/releases" >&2; exit 2 ;;
esac

if [ ! -d "$RELEASE_DIR" ]; then
  echo "release directory does not exist" >&2
  exit 2
fi
if [ ! -f "$DEPLOY_ROOT/.env.e2e" ]; then
  echo "$DEPLOY_ROOT/.env.e2e is missing" >&2
  exit 2
fi

chmod 600 "$DEPLOY_ROOT/.env.e2e"
ln -sfn "$DEPLOY_ROOT/.env.e2e" "$RELEASE_DIR/.env.e2e"

cd "$RELEASE_DIR"
docker compose \
  --project-name cuhabot-e2e \
  --env-file .env.e2e \
  -f docker-compose.e2e.yml \
  --profile discord-e2e \
  up -d --build e2e-db e2e-db-init e2e-bot

attempt=0
until curl --fail --silent --show-error http://127.0.0.1:8765/health >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then
    docker compose --project-name cuhabot-e2e -f docker-compose.e2e.yml logs --tail=120 e2e-bot >&2
    exit 1
  fi
  sleep 2
done

ln -sfn "$RELEASE_DIR" "$DEPLOY_ROOT/current"
echo "E2E release activated: $(basename "$RELEASE_DIR")"
