from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template, request

from crypto_pipeline.config import PipelineConfig
from crypto_pipeline.pipeline import CryptoPipeline


def _to_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except ValueError:
        return default


def create_app() -> Flask:
    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")

    config = PipelineConfig(
        top_n_coins=50,
        warehouse_path=Path("warehouse/crypto_market.db"),
        raw_lake_root=Path("data_lake/raw"),
    )
    pipeline = CryptoPipeline(config)

    @app.get("/")
    def index() -> str:
        snapshot = pipeline.warehouse.get_latest_snapshot(limit=50)
        symbols = pipeline.warehouse.get_available_symbols(limit=200)
        return render_template("index.html", initial_snapshot=snapshot, symbols=symbols)

    @app.post("/api/run-once")
    def run_once():
        top_n = _to_int(request.args.get("top_n"), pipeline.config.top_n_coins)
        pipeline.config.top_n_coins = top_n
        result = pipeline.run_once()
        return jsonify(result)

    @app.get("/api/latest")
    def latest_snapshot():
        limit = _to_int(request.args.get("limit"), 50)
        rows = pipeline.warehouse.get_latest_snapshot(limit=limit)
        return jsonify({"rows": rows, "count": len(rows)})

    @app.get("/api/series/<symbol>")
    def price_series(symbol: str):
        points = _to_int(request.args.get("points"), 240)
        rows = pipeline.warehouse.get_price_series(symbol=symbol, points=points)
        return jsonify({"symbol": symbol.upper(), "rows": rows, "count": len(rows)})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
