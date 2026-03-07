from __future__ import annotations

import time
from typing import Any

import requests

from .config import PipelineConfig


class CoinGeckoExtractor:
    def __init__(self, config: PipelineConfig):
        self.config = config

    def _request(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{self.config.api_base_url}{endpoint}"
        last_exc: Exception | None = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = requests.get(url, params=params, timeout=self.config.request_timeout_sec)
                if response.status_code == 429:
                    raise requests.HTTPError("Rate limited (429)", response=response)

                response.raise_for_status()
                data = response.json()
                if not isinstance(data, list):
                    raise ValueError("Expected list response from CoinGecko")
                return data
            except Exception as exc:  # broad catch keeps retry policy simple
                last_exc = exc
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_backoff_sec * attempt)
                else:
                    break

        if last_exc:
            raise RuntimeError(f"CoinGecko request failed after retries: {last_exc}") from last_exc
        raise RuntimeError("CoinGecko request failed for unknown reason")

    def fetch_market_snapshots(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page = 1

        while len(records) < self.config.top_n_coins:
            params = {
                "vs_currency": self.config.vs_currency,
                "order": "market_cap_desc",
                "per_page": min(self.config.per_page, self.config.top_n_coins),
                "page": page,
                "sparkline": str(self.config.include_sparkline).lower(),
                "price_change_percentage": "24h",
            }
            batch = self._request("/coins/markets", params)
            if not batch:
                break

            records.extend(batch)
            page += 1

        return records[: self.config.top_n_coins]
