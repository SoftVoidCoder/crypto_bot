#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/ft_common.sh"
exec "$FT" download-data --userdir ft_user_data --exchange bybit --trading-mode futures \
  --pairs BTC/USDT:USDT ADA/USDT:USDT DOGE/USDT:USDT --timeframes 15m --days "${1:-365}"
