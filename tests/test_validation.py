from __future__ import annotations

import json
from pathlib import Path

from crypto_pipeline.config import PipelineConfig
from crypto_pipeline.pipeline import CryptoPipeline
from crypto_pipeline.validation import CryptoValidationService


def test_market_snapshot_validation_rejects_bad_rows() -> None:
    validator = CryptoValidationService()
    rows = [
        {
            "coin_id": "bitcoin",
            "symbol": "BTC",
            "name": "Bitcoin",
            "snapshot_ts": "2026-03-07T00:00:00+00:00",
            "market_cap_rank": 1,
            "price": 70000.0,
            "market_cap": 1_300_000_000_000.0,
            "total_volume": 50_000_000_000.0,
            "price_change_24h_pct": 2.5,
        },
        {
            "coin_id": "",
            "symbol": "btc",
            "name": "",
            "snapshot_ts": "bad-date",
            "market_cap_rank": -2,
            "price": -1.0,
            "market_cap": -10,
            "total_volume": -50,
            "price_change_24h_pct": -500,
        },
    ]

    result = validator.validate_market_snapshot(rows)

    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert len(result.issues) >= 6


def test_price_series_validation_detects_duplicates_and_invalid_price() -> None:
    validator = CryptoValidationService()
    rows = [
        {
            "coin_id": "bitcoin",
            "price_ts": "2026-03-07T00:00:00+00:00",
            "price": 68000.0,
            "source_window": "sparkline_7d",
            "ingested_at": "2026-03-07T01:00:00+00:00",
        },
        {
            "coin_id": "bitcoin",
            "price_ts": "2026-03-07T00:00:00+00:00",
            "price": 68100.0,
            "source_window": "sparkline_7d",
            "ingested_at": "2026-03-07T01:00:00+00:00",
        },
        {
            "coin_id": "ethereum",
            "price_ts": "2026-03-07T01:00:00+00:00",
            "price": -10.0,
            "source_window": "sparkline_7d",
            "ingested_at": "2026-03-07T01:00:00+00:00",
        },
    ]

    result = validator.validate_price_series(rows)

    assert result.valid_count == 1
    assert result.invalid_count == 2
    assert any(issue.rule == "unique_key" for issue in result.issues)
    assert any(issue.field == "price" for issue in result.issues)


def test_pipeline_filters_invalid_rows_and_writes_validation_report(tmp_path: Path) -> None:
    config = PipelineConfig(
        warehouse_path=tmp_path / "warehouse" / "crypto_market.db",
        raw_lake_root=tmp_path / "data_lake" / "raw",
        top_n_coins=2,
    )
    pipeline = CryptoPipeline(config)

    # one valid coin + one invalid coin (negative price and malformed symbol)
    raw_records = [
        {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "market_cap_rank": 1,
            "current_price": 68000.0,
            "market_cap": 1_000_000_000.0,
            "total_volume": 100_000_000.0,
            "price_change_percentage_24h": 1.0,
            "circulating_supply": 19_000_000,
            "total_supply": 21_000_000,
            "max_supply": 21_000_000,
            "sparkline_in_7d": {"price": [67000.0, 68000.0, 68500.0]},
        },
        {
            "id": "badcoin",
            "symbol": "bad symbol",
            "name": "Bad Coin",
            "market_cap_rank": 999,
            "current_price": -1.0,
            "market_cap": -1,
            "total_volume": -5,
            "price_change_percentage_24h": 0.0,
            "circulating_supply": 0,
            "total_supply": 0,
            "max_supply": None,
            "sparkline_in_7d": {"price": [1.0, -2.0, 3.0]},
        },
    ]

    pipeline.extractor.fetch_market_snapshots = lambda: raw_records

    result = pipeline.run_once()

    assert result["coins_extracted"] == 2
    assert result["snapshot_rows_loaded"] == 1
    assert result["snapshot_rows_invalid"] == 1
    assert result["series_rows_invalid"] == 1

    validation_file = Path(result["validation_file"])
    assert validation_file.exists()

    report = json.loads(validation_file.read_text(encoding="utf-8"))
    assert report["market_snapshot"]["invalid_rows"] == 1
    assert report["price_series"]["invalid_rows"] == 1
