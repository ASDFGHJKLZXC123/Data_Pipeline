from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PipelineConfig:
    api_base_url: str = "https://api.coingecko.com/api/v3"
    vs_currency: str = "usd"
    top_n_coins: int = 50
    per_page: int = 250
    request_timeout_sec: int = 30
    max_retries: int = 3
    retry_backoff_sec: float = 2.0
    poll_interval_sec: int = 300
    include_sparkline: bool = True
    raw_lake_root: Path = Path("data_lake/raw")
    warehouse_path: Path = Path("warehouse/crypto_market.db")
