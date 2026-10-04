#!/usr/bin/env bash
# Container entrypoint for RegimeFlow on Render.
#
# Render gives us PORT and (optionally) secrets in the environment; everything
# else comes from the JSON configs baked into the image. Freqtrade reads
# FREQTRADE__<SECTION>__<KEY> variables and they override the JSON, which is why
# no secret is ever written into the repository.
set -euo pipefail

MODE="${BOT_MODE:-dry}"
USERDIR="${FREQTRADE_USERDIR:-/freqtrade/user_data}"
PORT="${PORT:-8080}"

log() { echo "[entrypoint] $*"; }

# Render only routes traffic to a process bound on 0.0.0.0:$PORT.
export FREQTRADE__API_SERVER__ENABLED="true"
export FREQTRADE__API_SERVER__LISTEN_IP_ADDRESS="0.0.0.0"
export FREQTRADE__API_SERVER__LISTEN_PORT="$PORT"

case "$MODE" in
  dry)
    CONFIGS=(--config "$USERDIR/config.base.json")
    DB="trades-dry.sqlite"
    ;;
  testnet)
    if [[ -z "${FREQTRADE__EXCHANGE__KEY:-}" || -z "${FREQTRADE__EXCHANGE__SECRET:-}" ]]; then
      log "FATAL: BOT_MODE=testnet requires FREQTRADE__EXCHANGE__KEY and FREQTRADE__EXCHANGE__SECRET"
      exit 2
    fi
    CONFIGS=(--config "$USERDIR/config.base.json" --config "$USERDIR/config.testnet.json")
    DB="trades-testnet.sqlite"
    ;;
  mainnet)
    if [[ "${FREQTRADE_REAL_CONFIRM:-}" != "I_UNDERSTAND_REAL_MONEY" ]]; then
      log "FATAL: BOT_MODE=mainnet is locked. Set FREQTRADE_REAL_CONFIRM=I_UNDERSTAND_REAL_MONEY to unlock."
      exit 2
    fi
    if [[ -z "${FREQTRADE__EXCHANGE__KEY:-}" || -z "${FREQTRADE__EXCHANGE__SECRET:-}" ]]; then
      log "FATAL: BOT_MODE=mainnet requires FREQTRADE__EXCHANGE__KEY and FREQTRADE__EXCHANGE__SECRET"
      exit 2
    fi
    CONFIGS=(--config "$USERDIR/config.base.json" --config "$USERDIR/config.mainnet.json")
    DB="trades-mainnet.sqlite"
    ;;
  *)
    log "FATAL: unknown BOT_MODE='$MODE' (expected dry, testnet or mainnet)"
    exit 2
    ;;
esac

# Render's free instances have an ephemeral filesystem, so keep the database at
# an absolute path inside user_data instead of relying on relative resolution.
export FREQTRADE__DB_URL="sqlite:///${USERDIR}/${DB}"

mkdir -p "$USERDIR/data" "$USERDIR/logs"

# FreqUI ships with the upstream image; verify instead of silently serving 404.
if ! python3 - <<'PY' >/dev/null 2>&1
import os, sys, freqtrade
p = os.path.join(os.path.dirname(freqtrade.__file__), "rpc", "api_server", "ui", "installed", "index.html")
sys.exit(0 if os.path.exists(p) else 1)
PY
then
  log "FreqUI not found in the image, installing (non-fatal if this fails)"
  freqtrade install-ui || log "WARN: freqtrade install-ui failed; REST API still works"
fi

log "mode=$MODE port=$PORT userdir=$USERDIR db=$DB"
log "starting: freqtrade trade ${CONFIGS[*]} --strategy RegimeFlowStrategy"

exec freqtrade trade --userdir "$USERDIR" "${CONFIGS[@]}" --strategy RegimeFlowStrategy
