from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any


@dataclass(slots=True)
class ValidationIssue:
    dataset: str
    row_index: int
    field: str
    rule: str
    message: str
    severity: str = "error"


@dataclass(slots=True)
class ValidationResult:
    dataset: str
    valid_rows: list[dict[str, Any]]
    invalid_rows: list[dict[str, Any]]
    issues: list[ValidationIssue]

    @property
    def valid_count(self) -> int:
        return len(self.valid_rows)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_rows)


class Rule:
    name = "rule"

    def validate(self, row: dict[str, Any]) -> str | None:
        raise NotImplementedError


class RequiredField(Rule):
    name = "required"

    def __init__(self, field: str):
        self.field = field

    def validate(self, row: dict[str, Any]) -> str | None:
        value = row.get(self.field)
        if value is None:
            return f"{self.field} is required"
        if isinstance(value, str) and not value.strip():
            return f"{self.field} must not be empty"
        return None


class NumericMin(Rule):
    name = "numeric_min"

    def __init__(self, field: str, min_value: float, allow_none: bool = True):
        self.field = field
        self.min_value = min_value
        self.allow_none = allow_none

    def validate(self, row: dict[str, Any]) -> str | None:
        value = row.get(self.field)
        if value is None:
            return None if self.allow_none else f"{self.field} is required"
        if not isinstance(value, (int, float)):
            return f"{self.field} must be numeric"
        if value < self.min_value:
            return f"{self.field} must be >= {self.min_value}"
        return None


class NumericRange(Rule):
    name = "numeric_range"

    def __init__(self, field: str, min_value: float, max_value: float, allow_none: bool = True):
        self.field = field
        self.min_value = min_value
        self.max_value = max_value
        self.allow_none = allow_none

    def validate(self, row: dict[str, Any]) -> str | None:
        value = row.get(self.field)
        if value is None:
            return None if self.allow_none else f"{self.field} is required"
        if not isinstance(value, (int, float)):
            return f"{self.field} must be numeric"
        if value < self.min_value or value > self.max_value:
            return f"{self.field} must be between {self.min_value} and {self.max_value}"
        return None


class RegexMatch(Rule):
    name = "regex_match"

    def __init__(self, field: str, pattern: str):
        self.field = field
        self.regex = re.compile(pattern)

    def validate(self, row: dict[str, Any]) -> str | None:
        value = row.get(self.field)
        if value is None:
            return f"{self.field} is required"
        if not isinstance(value, str) or not self.regex.fullmatch(value):
            return f"{self.field} is not in expected format"
        return None


class IsoTimestamp(Rule):
    name = "iso_timestamp"

    def __init__(self, field: str):
        self.field = field

    def validate(self, row: dict[str, Any]) -> str | None:
        value = row.get(self.field)
        if not isinstance(value, str):
            return f"{self.field} must be an ISO timestamp string"
        try:
            datetime.fromisoformat(value)
        except ValueError:
            return f"{self.field} must be a valid ISO timestamp"
        return None


class ValidationEngine:
    def __init__(self, dataset: str, rules: dict[str, list[Rule]], unique_keys: tuple[str, ...] | None = None):
        self.dataset = dataset
        self.rules = rules
        self.unique_keys = unique_keys

    def validate_rows(self, rows: list[dict[str, Any]]) -> ValidationResult:
        valid_rows: list[dict[str, Any]] = []
        invalid_rows: list[dict[str, Any]] = []
        issues: list[ValidationIssue] = []
        seen_keys: set[tuple[Any, ...]] = set()

        for idx, row in enumerate(rows):
            row_issues: list[ValidationIssue] = []

            for field, field_rules in self.rules.items():
                for rule in field_rules:
                    message = rule.validate(row)
                    if message:
                        row_issues.append(
                            ValidationIssue(
                                dataset=self.dataset,
                                row_index=idx,
                                field=field,
                                rule=rule.name,
                                message=message,
                            )
                        )

            if self.unique_keys:
                key = tuple(row.get(k) for k in self.unique_keys)
                if any(v is None for v in key):
                    row_issues.append(
                        ValidationIssue(
                            dataset=self.dataset,
                            row_index=idx,
                            field=",".join(self.unique_keys),
                            rule="unique_key",
                            message="unique key contains null values",
                        )
                    )
                elif key in seen_keys:
                    row_issues.append(
                        ValidationIssue(
                            dataset=self.dataset,
                            row_index=idx,
                            field=",".join(self.unique_keys),
                            rule="unique_key",
                            message="duplicate key in batch",
                        )
                    )
                else:
                    seen_keys.add(key)

            if row_issues:
                invalid_rows.append(row)
                issues.extend(row_issues)
            else:
                valid_rows.append(row)

        return ValidationResult(
            dataset=self.dataset,
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
            issues=issues,
        )


class CryptoValidationService:
    def __init__(self):
        self.snapshot_validator = ValidationEngine(
            dataset="market_snapshot",
            rules={
                "coin_id": [RequiredField("coin_id")],
                "symbol": [RequiredField("symbol"), RegexMatch("symbol", r"^[A-Z0-9]{2,15}$")],
                "name": [RequiredField("name")],
                "snapshot_ts": [RequiredField("snapshot_ts"), IsoTimestamp("snapshot_ts")],
                "market_cap_rank": [NumericMin("market_cap_rank", 1, allow_none=True)],
                "price": [NumericMin("price", 0, allow_none=False)],
                "market_cap": [NumericMin("market_cap", 0, allow_none=True)],
                "total_volume": [NumericMin("total_volume", 0, allow_none=True)],
                "price_change_24h_pct": [NumericRange("price_change_24h_pct", -100, 5000, allow_none=True)],
            },
            unique_keys=("coin_id", "snapshot_ts"),
        )

        self.series_validator = ValidationEngine(
            dataset="price_series",
            rules={
                "coin_id": [RequiredField("coin_id")],
                "price_ts": [RequiredField("price_ts"), IsoTimestamp("price_ts")],
                "price": [NumericMin("price", 0, allow_none=False)],
                "source_window": [RequiredField("source_window")],
                "ingested_at": [RequiredField("ingested_at"), IsoTimestamp("ingested_at")],
            },
            unique_keys=("coin_id", "price_ts", "source_window"),
        )

    def validate_market_snapshot(self, rows: list[dict[str, Any]]) -> ValidationResult:
        return self.snapshot_validator.validate_rows(rows)

    def validate_price_series(self, rows: list[dict[str, Any]]) -> ValidationResult:
        return self.series_validator.validate_rows(rows)
