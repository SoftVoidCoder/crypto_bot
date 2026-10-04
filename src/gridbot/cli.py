from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

import pandas as pd

from .backtest import run_backtest
from .data import BybitData
from .indicators import MLRegimeFilter, RuleRegimeFilter


def _load(path: str) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    return frame.set_index("timestamp").sort_index()


def _default_symbols() -> list[str]:
    return os.getenv("GRIDBOT_SYMBOLS", "BTCUSDT,ADAUSDT,DOGEUSDT").split(",")


def main() -> None:
    from dotenv import load_dotenv

    early = argparse.ArgumentParser(add_help=False)
    early.add_argument("--env-file", default=".env")
    selected, _ = early.parse_known_args()
    load_dotenv(selected.env_file, override=True)

    parser = argparse.ArgumentParser(prog="gridbot")
    parser.add_argument("--env-file", default=".env", help="credentials file, e.g. .env.testnet")
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download", help="download Bybit candles")
    download.add_argument("--symbols", nargs="+", default=_default_symbols())
    download.add_argument("--interval", default="15")
    download.add_argument("--limit", type=int, default=5000)
    download.add_argument("--out", default="data", help="output directory")

    backtest = commands.add_parser("backtest", help="run an event-driven grid backtest")
    backtest.add_argument("csv", nargs="+")
    backtest.add_argument("--filter", choices=("rules", "ml"), default="rules")
    backtest.add_argument("--equity", type=float, default=10_000)
    commands.add_parser("check", help="check private API credentials without placing orders")
    run = commands.add_parser("run", help="run paper/testnet/demo/mainnet grid engine")
    run.add_argument("--execute", action="store_true", help="place/cancel exchange orders")
    run.add_argument("--confirm-real", action="store_true", help="second mainnet execution confirmation")
    run.add_argument("--once", action="store_true", help="run one reconciliation cycle and exit")
    commands.add_parser("status", help="show equity, positions, and bot order counts")
    stop = commands.add_parser("stop", help="cancel bot orders and optionally flatten positions")
    stop.add_argument("--execute", action="store_true")
    stop.add_argument("--confirm-real", action="store_true")
    stop.add_argument("--flatten", action="store_true")
    commands.add_parser("reset", help="clear a persisted bot halt after reviewing its cause")
    args = parser.parse_args()

    if args.command == "download":
        output = Path(args.out)
        output.mkdir(parents=True, exist_ok=True)
        source = BybitData()
        for symbol in args.symbols:
            symbol = symbol.replace("/", "").upper()
            frame = source.klines(symbol, args.interval, limit=args.limit)
            path = output / f"{symbol}_{args.interval}.csv"
            frame.to_csv(path, index_label="timestamp")
            print(f"{symbol}: saved {len(frame)} candles to {path.resolve()}")
        return

    if args.command == "check":
        from .broker import BybitBroker

        broker = BybitBroker()
        print(f"{broker.environment}: connected, account equity {broker.account_equity():.2f} USDT")
        return

    if args.command in {"run", "status", "stop", "reset"}:
        from .runtime import LiveBot

        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        execute = getattr(args, "execute", False)
        confirm_real = getattr(args, "confirm_real", False)
        bot = LiveBot(execute=execute, confirm_real=confirm_real)
        if args.command == "run":
            bot.cycle() if args.once else bot.run_forever()
        elif args.command == "status":
            print(json.dumps(bot.status(), indent=2))
        elif args.command == "stop":
            bot.stop(flatten=args.flatten)
        else:
            bot.reset()
            print("persisted halt and anchors cleared")
        return

    for csv in args.csv:
        frame = _load(csv)
        if args.filter == "ml":
            split = int(len(frame) * 0.60)
            if split < 150 or len(frame) - split < 50:
                raise SystemExit(f"{csv}: ML backtest needs roughly 250+ candles")
            model = MLRegimeFilter().fit(frame.iloc[:split])
            tested = frame.iloc[split:]
            ranging = model.predict(tested)
        else:
            tested = frame
            ranging = RuleRegimeFilter().predict(frame)
        result = run_backtest(tested, ranging, args.equity)
        print(f"\n{Path(csv).stem}")
        print(f"  final equity: {result.final_equity:.2f}")
        print(f"  return:       {result.return_pct:.2f}%")
        print(f"  max drawdown: {result.max_drawdown_pct:.2f}%")
        print(f"  closed lots:  {result.trades}")
        print(f"  halted:       {result.halted_reason or 'no'}")


if __name__ == "__main__":
    main()
