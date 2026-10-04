#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FT="$ROOT_DIR/.freqtrade-venv/bin/freqtrade"

if [[ ! -x "$FT" ]]; then
  echo "Freqtrade не установлен: $FT" >&2
  exit 1
fi

cd "$ROOT_DIR"

if [[ -f .env.freqtrade ]]; then
  set -a
  source .env.freqtrade
  set +a
fi
