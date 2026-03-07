from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from crypto_pipeline.config import PipelineConfig
from crypto_pipeline.pipeline import CryptoPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Continuous cryptocurrency ETL pipeline (CoinGecko -> data lake -> SQLite warehouse)"
    )
    parser.add_argument("--mode", choices=["once", "daemon"], default="once")
    parser.add_argument("--top-n", type=int, default=50, help="Number of highest market-cap coins to ingest")
    parser.add_argument("--interval", type=int, default=300, help="Poll interval in seconds for daemon mode")
    parser.add_argument("--currency", default="usd", help="Quote currency (e.g., usd, eur)")
    parser.add_argument("--warehouse-path", default="warehouse/crypto_market.db")
    parser.add_argument("--raw-root", default="data_lake/raw")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    config = PipelineConfig(
        vs_currency=args.currency,
        top_n_coins=args.top_n,
        poll_interval_sec=args.interval,
        warehouse_path=Path(args.warehouse_path),
        raw_lake_root=Path(args.raw_root),
    )
    pipeline = CryptoPipeline(config)

    if args.mode == "once":
        result = pipeline.run_once()
        print(json.dumps(result, indent=2))
    else:
        pipeline.run_forever()


if __name__ == "__main__":
    main()
