#!/usr/bin/env bash
# Local-only simulation of the legacy Pages Function /api/monthly.
# SYNTHETIC data only; no Cloudflare credentials; nothing is deployed.
# Usage: WRANGLER=/path/to/wrangler tests/legacy_api_monthly/simulate.sh [extra `wrangler pages dev` args for the "withdb" run]
# Example (after the fix): tests/legacy_api_monthly/simulate.sh --binding LEGACY_D1_API_ENABLED=true
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WRANGLER="${WRANGLER:-npx wrangler}"
PORT="${PORT:-8788}"
WORK="$(mktemp -d)"
trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$WORK" "$ROOT/frontend/wrangler.sim.toml"' EXIT
cd "$ROOT/frontend" || exit 1
cat > wrangler.sim.toml <<EOT
name = "sim"
compatibility_date = "2026-09-01"
pages_build_output_dir = "dist"
[[d1_databases]]
binding = "DB"
database_name = "gold-housing"
database_id = "gold-housing"
EOT
run() { # $1=label $2=withdb(0/1) rest=extra args
  label=$1; withdb=$2; shift 2
  PORT=$((PORT+1)) # fresh port per run: a lingering workerd from the previous run must not answer
  CFG=""; [ "$withdb" = 1 ] && CFG="--d1 DB=gold-housing"
  $WRANGLER pages dev dist $CFG --local --port "$PORT" --persist-to "$WORK/state" "$@" >"$WORK/$label.log" 2>&1 &
  pid=$!
  for i in $(seq 1 40); do curl -s -o /dev/null "http://127.0.0.1:$PORT/" && break; sleep 1; done
  code=$(curl -s -o "$WORK/$label.body" -w '%{http_code}' "http://127.0.0.1:$PORT/api/monthly")
  echo "[$label] HTTP $code"; head -c 700 "$WORK/$label.body"; echo
  kill $pid 2>/dev/null; pkill -f -- "--port $PORT" 2>/dev/null; wait $pid 2>/dev/null; sleep 1
}
# (a) no D1 binding
run nobinding 0
# (b) synthetic local D1 incl. a SYNTHETIC gold_eur_oz series
$WRANGLER d1 execute gold-housing --local --config wrangler.sim.toml --persist-to "$WORK/state" --file ../db/migrations/0001_init.sql >/dev/null 2>&1
$WRANGLER d1 execute gold-housing --local --config wrangler.sim.toml --persist-to "$WORK/state" --command "INSERT INTO observations(series_id,period,value) VALUES ('nl_hpi','2000-01',50),('nl_house_avg_eur','2000-01',150000),('gold_eur_oz','2000-01',280),('nl_hpi','2000-02',55),('nl_house_avg_eur','2000-02',160000),('gold_eur_oz','2000-02',300)" >/dev/null 2>&1
run withdb 1 "$@"
