#!/usr/bin/env bash
# hey-based smoke test — quicker to run than full k6, less granular stats.
#
# Usage:  GENIOS_BASE_URL=... GENIOS_API_KEY=... ENTITY_NAME=... ./pull_api.hey.sh
#
# Runs ~50 req/s for 60s (not full 500 req/s — use k6 for that).

set -euo pipefail

: "${GENIOS_BASE_URL:?set GENIOS_BASE_URL}"
: "${GENIOS_API_KEY:?set GENIOS_API_KEY}"
ENTITY="${ENTITY_NAME:-Priya Sharma}"

BODY=$(cat <<EOF
{"entity":"${ENTITY}","situation":"load test","context_size":"medium"}
EOF
)

hey \
  -z 60s \
  -c 50 \
  -q 1 \
  -m POST \
  -H "Authorization: Bearer ${GENIOS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "${BODY}" \
  "${GENIOS_BASE_URL}/v1/context"
