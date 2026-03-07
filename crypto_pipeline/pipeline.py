from __future__ import annotations

import logging
import time
from dataclasses import asdict

from .config import PipelineConfig
from .extractor import CoinGeckoExtractor
from .raw_store import RawDataLake
from .transformer import ingestion_time_utc, transform_market_snapshot, transform_price_series
from .validation import CryptoValidationService
from .warehouse import Warehouse


class CryptoPipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.extractor = CoinGeckoExtractor(config)
        self.raw_store = RawDataLake(config)
        self.warehouse = Warehouse(config)
        self.validator = CryptoValidationService()

    def run_once(self) -> dict[str, object]:
        ingested_at = ingestion_time_utc()
        raw_records = self.extractor.fetch_market_snapshots()

        raw_path = self.raw_store.write(raw_records, ingested_at)
        snapshot_rows = transform_market_snapshot(raw_records, ingested_at)
        series_rows = transform_price_series(raw_records, ingested_at)

        snapshot_validation = self.validator.validate_market_snapshot(snapshot_rows)
        series_validation = self.validator.validate_price_series(series_rows)

        snapshots_loaded = self.warehouse.load_market_snapshot(snapshot_validation.valid_rows)
        series_loaded = self.warehouse.load_price_series(series_validation.valid_rows)

        validation_report = {
            "ingested_at": ingested_at.isoformat(),
            "market_snapshot": {
                "valid_rows": snapshot_validation.valid_count,
                "invalid_rows": snapshot_validation.invalid_count,
                "issues": [asdict(issue) for issue in snapshot_validation.issues[:200]],
            },
            "price_series": {
                "valid_rows": series_validation.valid_count,
                "invalid_rows": series_validation.invalid_count,
                "issues": [asdict(issue) for issue in series_validation.issues[:200]],
            },
        }
        validation_path = self.raw_store.write_validation_report(validation_report, ingested_at)

        return {
            "ingested_at": ingested_at.isoformat(),
            "coins_extracted": len(raw_records),
            "raw_file": str(raw_path),
            "validation_file": str(validation_path),
            "snapshot_rows_loaded": snapshots_loaded,
            "series_rows_loaded": series_loaded,
            "snapshot_rows_invalid": snapshot_validation.invalid_count,
            "series_rows_invalid": series_validation.invalid_count,
        }

    def run_forever(self) -> None:
        while True:
            try:
                result = self.run_once()
                logging.info("Pipeline cycle complete: %s", result)
            except Exception:
                logging.exception("Pipeline cycle failed")
            time.sleep(self.config.poll_interval_sec)
