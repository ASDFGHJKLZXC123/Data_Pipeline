# Crypto Market Data Pipeline

Automated ETL pipeline that continuously ingests cryptocurrency market data from CoinGecko, stores raw payloads in a data lake layout, and loads transformed records into a structured SQLite warehouse for analysis.

## Architecture

External API (CoinGecko)
-> Python extraction script
-> Data transformation
-> Raw storage (data lake)
-> Data warehouse (SQLite)
-> Analytics queries

## What the pipeline collects

For each coin snapshot:
- Coin name and symbol
- Current price
- Market capitalization
- 24h trading volume
- Ingestion timestamp
- 24h price change percentage
- Supply fields

For price-change-over-time:
- 7-day sparkline price points from CoinGecko (`sparkline_in_7d`)
- Expanded into `fact_price_series` with timestamps

## Project structure

- `main.py`: CLI entrypoint (`once` or continuous `daemon` mode)
- `app.py`: web interface + HTTP API on top of the same backend pipeline
- `crypto_pipeline/extractor.py`: API extraction logic
- `crypto_pipeline/transformer.py`: dataset shaping and time-series expansion
- `crypto_pipeline/validation.py`: validation framework + rules engine
- `crypto_pipeline/raw_store.py`: raw JSON landing zone writer
- `crypto_pipeline/warehouse.py`: SQLite schema and loading
- `crypto_pipeline/sql/analytics_queries.sql`: sample analysis SQL
- `tests/test_validation.py`: validation and pipeline integration tests

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run once

```bash
python3 main.py --mode once --top-n 50 --currency usd
```

Example output:

```json
{
  "ingested_at": "2026-03-06T12:00:00+00:00",
  "coins_extracted": 50,
  "raw_file": "data_lake/raw/coin_gecko/date=2026-03-06/hour=12/markets_20260306T120000Z.json",
  "snapshot_rows_loaded": 50,
  "series_rows_loaded": 8400
}
```

## Run continuously

```bash
python3 main.py --mode daemon --interval 300 --top-n 50
```

## Web interface

```bash
python3 app.py
```

Then open `http://localhost:8000`.

Features:
- Trigger ingestion (`POST /api/run-once`)
- View latest market snapshot (`GET /api/latest?limit=50`)
- View coin price series (`GET /api/series/<symbol>?points=240`)

## Data validation framework

The ETL now includes a dedicated rules engine that validates transformed rows before warehouse load.

- Row-level rules: required fields, numeric minimum/range checks, symbol format regex, ISO timestamps
- Batch-level rules: duplicate key detection
- Output behavior:
  - valid rows are loaded to warehouse
  - invalid rows are rejected from load
  - validation report is written to `data_lake/raw/validation/...`

`main.py --mode once` output now includes:
- `validation_file`
- `snapshot_rows_invalid`
- `series_rows_invalid`

## Run tests

```bash
pytest -q
```

## Query warehouse

```bash
sqlite3 warehouse/crypto_market.db < crypto_pipeline/sql/analytics_queries.sql
```

## Notes

- CoinGecko may rate-limit requests. Retry/backoff is implemented.
- SQLite is used as the warehouse for local analytics; replace with Postgres/BigQuery/Snowflake in production.
