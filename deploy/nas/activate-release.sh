#!/bin/sh
set -eu

PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
export PATH

DEPLOY_ROOT=/volume1/docker/cuhabot
RELEASE_DIR=${1:-}
COMPOSE=/usr/local/bin/docker-compose
PROJECT=cuhabot-nas

case "$RELEASE_DIR" in
  "$DEPLOY_ROOT"/releases/*) ;;
  *) echo "release must be below $DEPLOY_ROOT/releases" >&2; exit 2 ;;
esac

test -d "$RELEASE_DIR"
test -f "$DEPLOY_ROOT/.env.nas"
test -x "$COMPOSE"

# Synology's Docker daemon rejects bind mounts whose host directory does not
# already exist, unlike newer Docker installations that create them.
mkdir -p "$DEPLOY_ROOT/postgres" "$DEPLOY_ROOT/backups"
chmod 700 "$DEPLOY_ROOT/backups"

PREVIOUS=$(readlink -f "$DEPLOY_ROOT/current" 2>/dev/null || true)
MUTATION_STARTED=0
chmod 600 "$DEPLOY_ROOT/.env.nas"
ln -sfn "$DEPLOY_ROOT/.env.nas" "$RELEASE_DIR/.env.nas"

compose() {
  "$COMPOSE" -p "$PROJECT" --env-file .env.nas -f docker-compose.nas.yml "$@"
}

rollback() {
  trap - EXIT INT TERM HUP
  echo "NAS release activation failed" >&2
  /usr/local/bin/docker kill --signal=SIGCONT cuhabot-nas-bot >/dev/null 2>&1 || true
  if [ "$MUTATION_STARTED" -eq 1 ] && [ -n "$PREVIOUS" ] && [ -d "$PREVIOUS" ]; then
    cd "$PREVIOUS"
    ln -sfn "$DEPLOY_ROOT/.env.nas" .env.nas
    compose up -d --build db bot || true
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
compose config >/dev/null
compose up -d db
compose build db-init bot
if [ -n "$PREVIOUS" ]; then
  # Build first. Freeze admissions only for the final idle check + migration.
  # The legacy Bot has no maintenance endpoint; its complete startup/session
  # log plus a settled save window is required, never just container health.
  # Each release carries the proof relevant to its mutation. Historical proof
  # files are not copied forward as if they were rerun against this image.
  for PROOF in monster-connectivity-verified.json; do
    test -f "$RELEASE_DIR/$PROOF"
    /usr/local/bin/docker run --rm --entrypoint python \
      -v "$RELEASE_DIR/$PROOF:/proof.json:ro" cuhabot-nas_bot \
      -c 'import json; assert json.load(open("/proof.json"))["passed"] is True'
  done
  /usr/local/bin/docker kill --signal=SIGSTOP cuhabot-nas-bot >/dev/null
  STAMP=$(date -u +%Y%m%dT%H%M%SZ)
  IDLE_LOG="$DEPLOY_ROOT/backups/idle-$STAMP.log"
  umask 077
  /usr/local/bin/docker logs cuhabot-nas-bot >"$IDLE_LOG" 2>&1
  /usr/local/bin/docker run --rm -i --entrypoint python cuhabot-nas_bot \
    deploy/nas/check_idle.py <"$IDLE_LOG"
  /usr/local/bin/docker exec cuhabot-nas-db sh -ec \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
    >"$DEPLOY_ROOT/backups/pre-beginner-$STAMP.dump"
  compose run --rm --entrypoint python db-init scripts/fingerprint_beginner_progress.py \
    >"$RELEASE_DIR/progress-before.json"
fi
MUTATION_STARTED=1
compose run --rm db-init
if [ -n "$PREVIOUS" ]; then
  compose run --rm --entrypoint python db-init scripts/fingerprint_beginner_progress.py \
    >"$RELEASE_DIR/progress-after.json"
  /usr/local/bin/docker run --rm --entrypoint python \
    -v "$RELEASE_DIR:/proof:ro" cuhabot-nas_bot \
    -c 'import json; a=json.load(open("/proof/progress-before.json")); b=json.load(open("/proof/progress-after.json")); assert a == b, "User progress changed during migration"; print("Progress preserved:", len(a), "tables")'
fi
# Keep admissions frozen until Compose replaces the verified-idle old process.
# Docker's stop timeout handles this frozen process; do not reopen a race here.
compose up -d bot

attempt=0
while :; do
  status=$(/usr/local/bin/docker inspect --format '{{.State.Health.Status}}' cuhabot-nas-bot 2>/dev/null || true)
  case "$status" in
    healthy) break ;;
    unhealthy)
      compose logs --tail=150 bot >&2 || true
      exit 1
      ;;
  esac
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 40 ]; then
    compose logs --tail=150 bot >&2 || true
    exit 1
  fi
  sleep 5
done

ln -sfn "$RELEASE_DIR" "$DEPLOY_ROOT/current"
trap - EXIT INT TERM HUP
echo "NAS release activated: $(basename "$RELEASE_DIR")"
