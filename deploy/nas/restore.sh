#!/bin/sh
set -eu

PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
export PATH

if [ "$#" -ne 2 ] || [ "$1" != "--execute" ]; then
  echo "usage: $0 --execute /volume1/docker/cuhabot/backups/cuhabot-*.dump" >&2
  exit 2
fi

DEPLOY_ROOT=/volume1/docker/cuhabot
BACKUP=$2
CURRENT=$(readlink -f "$DEPLOY_ROOT/current")
COMPOSE=/usr/local/bin/docker-compose

case "$BACKUP" in
  "$DEPLOY_ROOT"/backups/cuhabot-*.dump) ;;
  *) echo "backup must be below $DEPLOY_ROOT/backups" >&2; exit 2 ;;
esac
test -f "$BACKUP"

cd "$CURRENT"
"$COMPOSE" -p cuhabot-nas --env-file .env.nas -f docker-compose.nas.yml stop bot
"$COMPOSE" -p cuhabot-nas --env-file .env.nas -f docker-compose.nas.yml exec -T db \
  sh -ec 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB"; createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
"$COMPOSE" -p cuhabot-nas --env-file .env.nas -f docker-compose.nas.yml exec -T db \
  sh -ec 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < "$BACKUP"
"$COMPOSE" -p cuhabot-nas --env-file .env.nas -f docker-compose.nas.yml start bot
