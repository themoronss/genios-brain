#!/usr/bin/env bash
# Local development against a REAL copy of production — fast, and nothing touches prod.
#
# Why: from a laptop every query to Supabase (Singapore) is a ~80 ms round trip, and L2/L3/L4 make
# thousands of them one at a time, so a 5-minute server pass takes hours locally. A local copy
# answers in ~0.1 ms, so the same code on the same data runs at server speed or faster.
#
#   scripts/dev_localdb.sh start              start the local Postgres (port 5433)
#   scripts/dev_localdb.sh refresh            copy prod -> local (public schema), then migrate
#   scripts/dev_localdb.sh migrate            apply this checkout's migrations to the local copy
#   scripts/dev_localdb.sh run <org_id>       L2 -> L3/L4 -> cards for one org, on the local copy
#   scripts/dev_localdb.sh psql               open psql on the local copy
#   scripts/dev_localdb.sh url                print the local DATABASE_URL (for uvicorn etc.)
#   scripts/dev_localdb.sh stop | destroy     stop the server | delete the copy (real tenant data)
#
# The prod URL is read from .env and never modified. Everything local uses GENIOS_DATABASE_URL
# overridden in the environment, which pydantic-settings prefers over .env.
set -euo pipefail

PG_BIN="${PG_BIN:-/opt/homebrew/opt/postgresql@17/bin}"
ROOT="${GENIOS_LOCALDB_DIR:-$HOME/.genios-localdb}"
PORT="${GENIOS_LOCALDB_PORT:-5433}"
DB="genios_local"
LOCAL_URL="postgresql+psycopg://postgres@localhost:${PORT}/${DB}"
BRAIN="$(cd "$(dirname "$0")/.." && pwd)"

prod_url() {
  grep '^GENIOS_DATABASE_URL=' "$BRAIN/.env" | cut -d= -f2- | sed 's/+psycopg//'
}

start() {
  mkdir -p "$ROOT"
  if [ ! -d "$ROOT/data" ]; then
    "$PG_BIN/initdb" -D "$ROOT/data" -U postgres --auth=trust >/dev/null
  fi
  if ! "$PG_BIN/pg_ctl" -D "$ROOT/data" status >/dev/null 2>&1; then
    "$PG_BIN/pg_ctl" -D "$ROOT/data" -l "$ROOT/server.log" -w start \
      -o "-p $PORT -c listen_addresses=localhost -c unix_socket_directories='' \
          -c shared_buffers=512MB -c work_mem=32MB -c max_connections=200" >/dev/null
  fi
  echo "local postgres up on :$PORT"
}

migrate() {
  (cd "$BRAIN" && GENIOS_DATABASE_URL="$LOCAL_URL" PYTHONPATH=. .venv/bin/python -c \
    "from genios_engine.platform.migrate import apply_migrations as a; a(database_url='$LOCAL_URL'); print('migrations applied')")
}

refresh() {
  start
  local dump="$ROOT/prod_public.dump"
  echo "dumping prod (public schema) -> $dump ..."
  "$PG_BIN/pg_dump" "$(prod_url)" -n public -Fc --no-owner --no-privileges -f "$dump.tmp"
  mv "$dump.tmp" "$dump"
  restore
}

# Back to the state of the last dump, without touching prod — so every experiment starts from the
# same baseline and two runs can be compared.
restore() {
  start
  local dump="$ROOT/prod_public.dump"
  [ -f "$dump" ] || { echo "no dump yet — run: $0 refresh"; exit 1; }
  echo "restoring into $DB ..."
  "$PG_BIN/dropdb" -h localhost -p "$PORT" -U postgres --if-exists "$DB"
  "$PG_BIN/createdb" -h localhost -p "$PORT" -U postgres "$DB"
  "$PG_BIN/pg_restore" -h localhost -p "$PORT" -U postgres -d "$DB" --no-owner --no-privileges \
    -j 4 "$dump" || echo "(pg_restore reported warnings — see above)"
  # A copied job that prod was running is not running here; leave nothing that looks active.
  "$PG_BIN/psql" -h localhost -p "$PORT" -U postgres -d "$DB" -qc \
    "update sync_jobs set status='failed' where status in ('queued','running')" || true
  migrate
  echo "local copy ready: $LOCAL_URL"
}

run() {
  local org="${1:?usage: run <org_id>}"
  start
  # Nothing a local run does may leave the laptop as if it were production: no analytics events,
  # no ops alerts. (Outbound card delivery is outbox-enqueued and only the server drains it.)
  # Every LLM decision's prompt and answer lands in one folder per run, for reading a DEFER.
  local debug="$ROOT/llm_debug/$(date +%Y%m%d-%H%M%S)"
  echo "LLM decision prompts/answers -> $debug"
  (cd "$BRAIN" && GENIOS_DATABASE_URL="$LOCAL_URL" GENIOS_DEV_ORG="$org" \
    GENIOS_POSTHOG_API_KEY="" GENIOS_OPS_ALERT_WEBHOOK="" \
    GENIOS_L4_LLM_DECISION_DEBUG_DIR="$debug" PYTHONPATH=. \
    .venv/bin/python -u scripts/dev_run_l234.py)
}

case "${1:-}" in
  start) start ;;
  refresh) refresh ;;
  restore) restore ;;
  migrate) start; migrate ;;
  run) shift; run "$@" ;;
  app-cards)
    # What the Mac app would show: the real GET /cards + /cards/{id} handlers, no server started.
    start
    (cd "$BRAIN" && GENIOS_DATABASE_URL="$LOCAL_URL" GENIOS_DEV_ORG="${2:?usage: app-cards <org_id>}" \
      GENIOS_REDIS_URL="" GENIOS_POSTHOG_API_KEY="" GENIOS_OPS_ALERT_WEBHOOK="" \
      GENIOS_SCHEDULER_ENABLED=false PYTHONPATH=. .venv/bin/python scripts/dev_app_cards.py) \
      && open "${GENIOS_DEV_OUT:-$ROOT/app_cards}/cards.html" ;;
  psql) start; "$PG_BIN/psql" -h localhost -p "$PORT" -U postgres -d "$DB" ;;
  url) echo "$LOCAL_URL" ;;
  stop) "$PG_BIN/pg_ctl" -D "$ROOT/data" -m fast stop ;;
  destroy) "$PG_BIN/pg_ctl" -D "$ROOT/data" -m fast stop 2>/dev/null || true; rm -rf "$ROOT"; echo "deleted $ROOT" ;;
  *) sed -n '2,18p' "$0"; exit 1 ;;
esac
