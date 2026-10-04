#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/ft_common.sh"
exec "$FT" trade --userdir ft_user_data --config ft_user_data/config.base.json --strategy RegimeFlowStrategy
