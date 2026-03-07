from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def transform_market_snapshot(records: list[dict[str, Any]], ingested_at: datetime) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    for row in records:
        output.append(
            {
                "coin_id": row.get("id"),
                "symbol": (row.get("symbol") or "").upper(),
                "name": row.get("name"),
                "market_cap_rank": row.get("market_cap_rank"),
                "snapshot_ts": ingested_at.isoformat(),
                "price": _to_float(row.get("current_price")),
                "market_cap": _to_float(row.get("market_cap")),
                "total_volume": _to_float(row.get("total_volume")),
                "price_change_24h_pct": _to_float(row.get("price_change_percentage_24h")),
                "circulating_supply": _to_float(row.get("circulating_supply")),
                "total_supply": _to_float(row.get("total_supply")),
                "max_supply": _to_float(row.get("max_supply")),
            }
        )

    return output


def transform_price_series(records: list[dict[str, Any]], ingested_at: datetime) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []

    for row in records:
        coin_id = row.get("id")
        sparkline_prices = (row.get("sparkline_in_7d") or {}).get("price", [])
        if not coin_id or not sparkline_prices:
            continue

        total_points = len(sparkline_prices)
        window_start = ingested_at - timedelta(days=7)

        for i, price in enumerate(sparkline_prices):
            point_time = window_start + timedelta(seconds=(i / max(total_points - 1, 1)) * 7 * 24 * 3600)
            points.append(
                {
                    "coin_id": coin_id,
                    "price_ts": point_time.astimezone(timezone.utc).isoformat(),
                    "price": _to_float(price),
                    "source_window": "sparkline_7d",
                    "ingested_at": ingested_at.astimezone(timezone.utc).isoformat(),
                }
            )

    return points


def ingestion_time_utc() -> datetime:
    return datetime.now(timezone.utc)
