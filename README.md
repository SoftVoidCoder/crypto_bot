# Bybit trading workspace

Основная версия теперь построена на проверенном Freqtrade/FreqUI. Русская инструкция:
[FREQTRADE_RU.md](FREQTRADE_RU.md). Старый самописный GridPilot ниже сохранён как
исследовательский прототип и не является рекомендуемым торговым движком.

# Bybit USDT Grid Bot MVP (старый прототип)

Paper-first research scaffold for a neutral futures grid. It contains Bybit V5 candle download, an ADX/ATR or logistic-regression regime filter, position/drawdown limits, order-grid generation, and an event-driven backtest.

> This is research code, not a profit guarantee. Futures can liquidate the account. Start with historical tests, then testnet, and only then consider small real size.

## Architecture

```text
src/gridbot/
  data.py        Bybit V5 historical candles
  indicators.py ADX/ATR features and rule/ML regime filters
  strategy.py   symmetric grid construction
  risk.py       drawdown and daily-loss circuit breakers
  backtest.py   candle-level fill simulation with fees/slippage
  broker.py     guarded Bybit order adapter for testnet/live
  cli.py        download and backtest commands
tests/           one compact core check
```

## Run

Use Python 3.11–3.13 (the current `pybit` stack is not yet a safe bet on 3.14):

```bash
uv sync --extra dev
uv run gridbot download --symbols BTCUSDT ADAUSDT DOGEUSDT --interval 15 --limit 5000 --out data
uv run gridbot backtest data/*.csv --filter rules
uv run gridbot backtest data/*.csv --filter ml
uv run pytest
```

Bybit symbols do not contain `/`: use `BTCUSDT`, `ADAUSDT`, and `DOGEUSDT` (`DOGI` is a typo). The default list can be changed in `.env` with `GRIDBOT_SYMBOLS=...`.

`MLRegimeFilter` trains on the first 60% and trades only the final 40%. Do not shuffle time series. For serious evaluation use walk-forward folds, keep a final untouched test period, include fees/funding/slippage, and choose thresholds before looking at test results.

## Paper and live safety

The candle simulator is the paper mode in this MVP. Copy `.env.example` to `.env`; it is loaded automatically. Set `BYBIT_ENV` to one of:

- `paper` — local simulation, no keys;
- `testnet` — keys created on the separate Bybit Testnet website;
- `demo` — keys created after switching the production account to Demo Trading;
- `mainnet` — production keys and real money.

Check a private connection without placing orders with `uv run gridbot check`. Mainnet reads are allowed, but real-money order writes remain blocked unless `GRIDBOT_LIVE_CONFIRM=true`. Use a dedicated subaccount and an API key with contract order/position permissions but without withdrawal permission.

Keep environments separate:

```bash
cp .env.testnet.example .env.testnet
cp .env.mainnet.example .env.mainnet
chmod 600 .env.testnet .env.mainnet
uv run gridbot --env-file .env.testnet check
uv run gridbot --env-file .env.mainnet check
```

Never paste keys into chat, source code, logs, or commits. Revoke any key whose secret was exposed and create a replacement.

## Live commands

Paper plan, with no private API calls or exchange orders:

```bash
BYBIT_ENV=paper uv run gridbot --env-file /dev/null run
```

Testnet smoke test and continuous execution:

```bash
uv run gridbot --env-file .env.testnet run --once
uv run gridbot --env-file .env.testnet run --once --execute
uv run gridbot --env-file .env.testnet run --execute
uv run gridbot --env-file .env.testnet status
uv run gridbot --env-file .env.testnet stop --execute
```

Mainnet is intentionally double locked. It needs both `GRIDBOT_LIVE_CONFIRM=true` in `.env.mainnet` and the `--execute --confirm-real` command flags. Do not enable it before a multi-day Testnet soak test. `stop --execute --flatten` cancels bot-tagged orders and market-closes positions; use it only on a dedicated bot subaccount.

The account must use one-way position mode. Hedge mode is rejected explicitly because its `positionIdx` semantics differ and silently mixing the modes would place the wrong orders.

Runtime state is written atomically under `state/`. `reset` clears a reviewed halt and grid anchors. On each closed candle the bot refreshes REST truth, applies the portfolio drawdown/daily-loss circuit breakers, divides the configured exposure across all symbols, and replaces only orders tagged with the `gridbot-` prefix. The public WebSocket uses pybit's automatic reconnect/resubscribe and a stale-feed REST reconciliation fallback.

## Desktop app

Run the cross-platform dark desktop interface:

```bash
uv sync --extra ui
uv run gridbot-ui
```

Build on the target operating system (PyInstaller does not cross-compile):

```bash
./scripts/build_linux.sh
```

```powershell
.\scripts\build_windows.ps1
```

Linux output is `dist/GridPilot/GridPilot`; Windows output is `dist\GridPilot\GridPilot.exe`. Keep `.env.testnet` and `.env.mainnet` beside the executable's working directory. The UI never displays API keys. Testnet starts exchange execution directly; Mainnet additionally requires the environment lock and typing `MAINNET` in a confirmation dialog.

Each current backtest treats its equity independently. Before trading several symbols from one account, add a portfolio-level exposure cap so three grids cannot each allocate the full account limit.

The order endpoint only acknowledges acceptance; production execution must reconcile fills from the private order/execution WebSocket and periodically compare positions/open orders over REST. The official `pybit` WebSocket already pings, reconnects, authenticates, and resubscribes. Add a stale-message watchdog and REST reconciliation before running a continuous live loop.

## Known simulation limits

- OHLC candles do not reveal intrabar event order; entries never take profit on their entry candle to avoid optimistic fills.
- Funding, liquidation tiers, partial fills, queue position, maintenance margin, and exchange outages are not modeled.
- Latency is rarely the first bottleneck for a 15-minute grid. Keep one persistent client, consume WebSockets, avoid rebuilding unchanged orders, batch reconciliation, and measure before optimizing.
