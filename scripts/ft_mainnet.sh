#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/ft_common.sh"

if [[ "${FREQTRADE_REAL_CONFIRM:-}" != "I_UNDERSTAND_REAL_MONEY" ]]; then
  echo "Mainnet заблокирован. Для осознанного запуска задайте FREQTRADE_REAL_CONFIRM=I_UNDERSTAND_REAL_MONEY" >&2
  exit 2
fi

set -a
source .env.mainnet
set +a
export FREQTRADE__EXCHANGE__KEY="$BYBIT_API_KEY"
export FREQTRADE__EXCHANGE__SECRET="$BYBIT_API_SECRET"
exec "$FT" trade --userdir ft_user_data --config ft_user_data/config.base.json \
  --config ft_user_data/config.mainnet.json --strategy RegimeFlowStrategy
