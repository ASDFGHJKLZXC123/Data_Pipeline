from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import PipelineConfig


class RawDataLake:
    def __init__(self, config: PipelineConfig):
        self.config = config

    def write(self, payload: list[dict[str, Any]], ingested_at: datetime) -> Path:
        ts = ingested_at.astimezone(timezone.utc)
        day = ts.strftime("%Y-%m-%d")
        hour = ts.strftime("%H")
        stamp = ts.strftime("%Y%m%dT%H%M%SZ")

        target_dir = self.config.raw_lake_root / "coin_gecko" / f"date={day}" / f"hour={hour}"
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / f"markets_{stamp}.json"
        with target_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2)

        return target_file

    def write_validation_report(self, payload: dict[str, Any], ingested_at: datetime) -> Path:
        ts = ingested_at.astimezone(timezone.utc)
        day = ts.strftime("%Y-%m-%d")
        hour = ts.strftime("%H")
        stamp = ts.strftime("%Y%m%dT%H%M%SZ")

        target_dir = self.config.raw_lake_root / "validation" / f"date={day}" / f"hour={hour}"
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / f"validation_{stamp}.json"
        with target_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2)

        return target_file
