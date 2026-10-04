#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/ft_common.sh"

set -a
source .env.mainnet
set +a
export FREQTRADE__EXCHANGE__KEY="$BYBIT_API_KEY"
export FREQTRADE__EXCHANGE__SECRET="$BYBIT_API_SECRET"
exec "$FT" trade --userdir ft_user_data --config ft_user_data/config.base.json \
  --config ft_user_data/config.mainnet.json --strategy RegimeFlowStrategy
