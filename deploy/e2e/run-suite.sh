#!/bin/sh
set -eu

SUITE=${1:-all}
DEPLOY_ROOT=/home/vulpo/CUHABot-e2e
API_TOKEN=$(sed -n 's/^E2E_API_TOKEN=//p' "$DEPLOY_ROOT/.env.e2e")
AUTH_HEADER="Authorization: Bearer $API_TOKEN"

RUN_ID=$(
  curl --fail --silent --show-error \
    -H "$AUTH_HEADER" \
    -H 'Content-Type: application/json' \
    -d "{\"suite\":\"$SUITE\"}" \
    http://127.0.0.1:8765/v1/test-runs \
  | jq -r .run_id
)

while :; do
  RESULT=$(curl --fail --silent --show-error \
    -H "$AUTH_HEADER" \
    "http://127.0.0.1:8765/v1/test-runs/$RUN_ID")
  STATUS=$(printf '%s' "$RESULT" | jq -r .status)
  case "$STATUS" in
    passed|failed)
      printf '%s' "$RESULT" | jq '{run_id,suite,status,checks}'
      test "$STATUS" = passed
      exit
      ;;
  esac
  sleep 2
done
