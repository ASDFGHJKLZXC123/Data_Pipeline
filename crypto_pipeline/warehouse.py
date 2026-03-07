from __future__ import annotations

import sqlite3

from .config import PipelineConfig


class Warehouse:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._ensure_parent()
        self._init_schema()

    def _ensure_parent(self) -> None:
        self.config.warehouse_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.config.warehouse_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def _init_schema(self) -> None:
        with self.connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS dim_coin (
                    coin_key INTEGER PRIMARY KEY AUTOINCREMENT,
                    coin_id TEXT NOT NULL UNIQUE,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS fact_market_snapshot (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coin_key INTEGER NOT NULL,
                    snapshot_ts TEXT NOT NULL,
                    market_cap_rank INTEGER,
                    price_usd REAL,
                    market_cap_usd REAL,
                    volume_24h_usd REAL,
                    price_change_24h_pct REAL,
                    circulating_supply REAL,
                    total_supply REAL,
                    max_supply REAL,
                    UNIQUE (coin_key, snapshot_ts),
                    FOREIGN KEY (coin_key) REFERENCES dim_coin (coin_key)
                );

                CREATE TABLE IF NOT EXISTS fact_price_series (
                    series_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coin_key INTEGER NOT NULL,
                    price_ts TEXT NOT NULL,
                    price_usd REAL,
                    source_window TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    UNIQUE (coin_key, price_ts, source_window),
                    FOREIGN KEY (coin_key) REFERENCES dim_coin (coin_key)
                );

                CREATE INDEX IF NOT EXISTS idx_snapshot_time ON fact_market_snapshot (snapshot_ts);
                CREATE INDEX IF NOT EXISTS idx_snapshot_rank ON fact_market_snapshot (market_cap_rank);
                CREATE INDEX IF NOT EXISTS idx_series_time ON fact_price_series (price_ts);
                """
            )

    def _upsert_coin(self, con: sqlite3.Connection, coin_id: str, symbol: str, name: str) -> int:
        con.execute(
            """
            INSERT INTO dim_coin (coin_id, symbol, name)
            VALUES (?, ?, ?)
            ON CONFLICT (coin_id) DO UPDATE
            SET symbol = excluded.symbol,
                name = excluded.name
            """,
            (coin_id, symbol, name),
        )
        row = con.execute("SELECT coin_key FROM dim_coin WHERE coin_id = ?", (coin_id,)).fetchone()
        if row is None:
            raise RuntimeError(f"Failed to resolve coin_key for coin_id={coin_id}")
        return int(row[0])

    def load_market_snapshot(self, rows: list[dict[str, object]]) -> int:
        inserted = 0
        with self.connect() as con:
            for row in rows:
                coin_id = row.get("coin_id")
                symbol = row.get("symbol")
                name = row.get("name")
                if not coin_id or not symbol or not name:
                    continue

                coin_key = self._upsert_coin(con, str(coin_id), str(symbol), str(name))
                con.execute(
                    """
                    INSERT OR REPLACE INTO fact_market_snapshot (
                        coin_key, snapshot_ts, market_cap_rank, price_usd, market_cap_usd,
                        volume_24h_usd, price_change_24h_pct, circulating_supply, total_supply, max_supply
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        coin_key,
                        row.get("snapshot_ts"),
                        row.get("market_cap_rank"),
                        row.get("price"),
                        row.get("market_cap"),
                        row.get("total_volume"),
                        row.get("price_change_24h_pct"),
                        row.get("circulating_supply"),
                        row.get("total_supply"),
                        row.get("max_supply"),
                    ),
                )
                inserted += 1
        return inserted

    def load_price_series(self, rows: list[dict[str, object]]) -> int:
        inserted = 0
        with self.connect() as con:
            for row in rows:
                coin_id = row.get("coin_id")
                if not coin_id:
                    continue

                dim_row = con.execute("SELECT coin_key FROM dim_coin WHERE coin_id = ?", (coin_id,)).fetchone()
                if dim_row is None:
                    continue

                cursor = con.execute(
                    """
                    INSERT OR IGNORE INTO fact_price_series (
                        coin_key, price_ts, price_usd, source_window, ingested_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        int(dim_row[0]),
                        row.get("price_ts"),
                        row.get("price"),
                        row.get("source_window"),
                        row.get("ingested_at"),
                    ),
                )
                inserted += int(cursor.rowcount > 0)

        return inserted

    def get_latest_snapshot(self, limit: int = 50) -> list[dict[str, object]]:
        with self.connect() as con:
            latest_ts_row = con.execute("SELECT MAX(snapshot_ts) AS max_ts FROM fact_market_snapshot").fetchone()
            if latest_ts_row is None or latest_ts_row["max_ts"] is None:
                return []

            rows = con.execute(
                """
                SELECT
                    c.coin_id,
                    c.symbol,
                    c.name,
                    s.market_cap_rank,
                    s.price_usd,
                    s.market_cap_usd,
                    s.volume_24h_usd,
                    s.price_change_24h_pct,
                    s.snapshot_ts
                FROM fact_market_snapshot s
                JOIN dim_coin c ON c.coin_key = s.coin_key
                WHERE s.snapshot_ts = ?
                ORDER BY s.market_cap_rank ASC
                LIMIT ?
                """,
                (latest_ts_row["max_ts"], limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_available_symbols(self, limit: int = 200) -> list[str]:
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT DISTINCT c.symbol
                FROM dim_coin c
                JOIN fact_price_series p ON p.coin_key = c.coin_key
                ORDER BY c.symbol ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [str(row["symbol"]) for row in rows]

    def get_price_series(self, symbol: str, points: int = 240) -> list[dict[str, object]]:
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT c.symbol, c.name, p.price_ts, p.price_usd
                FROM fact_price_series p
                JOIN dim_coin c ON c.coin_key = p.coin_key
                WHERE c.symbol = UPPER(?)
                ORDER BY p.price_ts DESC
                LIMIT ?
                """,
                (symbol, points),
            ).fetchall()

        # return chronological order for plotting
        return [dict(row) for row in reversed(rows)]
