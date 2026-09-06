#!/bin/sh
set -eu

PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
export PATH

DEPLOY_ROOT=/volume1/docker/cuhabot
CURRENT=$(readlink -f "$DEPLOY_ROOT/current")
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR="$DEPLOY_ROOT/backups"
COMPOSE=/usr/local/bin/docker-compose

test -d "$CURRENT"
test -f "$DEPLOY_ROOT/.env.nas"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
cd "$CURRENT"

"$COMPOSE" -p cuhabot-nas --env-file .env.nas -f docker-compose.nas.yml \
  exec -T db sh -ec 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  > "$BACKUP_DIR/cuhabot-$STAMP.dump"

chmod 600 "$BACKUP_DIR/cuhabot-$STAMP.dump"
find "$BACKUP_DIR" -type f -name 'cuhabot-*.dump' -mtime +30 -delete
echo "$BACKUP_DIR/cuhabot-$STAMP.dump"
