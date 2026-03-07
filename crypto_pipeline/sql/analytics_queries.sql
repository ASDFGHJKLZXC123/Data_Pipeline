-- Top 10 coins by latest market capitalization
WITH latest_snapshot AS (
    SELECT MAX(snapshot_ts) AS max_ts FROM fact_market_snapshot
)
SELECT c.coin_id, c.symbol, c.name, s.market_cap_rank, s.price_usd, s.market_cap_usd, s.volume_24h_usd
FROM fact_market_snapshot s
JOIN dim_coin c ON c.coin_key = s.coin_key
JOIN latest_snapshot l ON l.max_ts = s.snapshot_ts
ORDER BY s.market_cap_usd DESC
LIMIT 10;

-- 24h movers in the latest snapshot
WITH latest_snapshot AS (
    SELECT MAX(snapshot_ts) AS max_ts FROM fact_market_snapshot
)
SELECT c.symbol, c.name, s.price_usd, s.price_change_24h_pct
FROM fact_market_snapshot s
JOIN dim_coin c ON c.coin_key = s.coin_key
JOIN latest_snapshot l ON l.max_ts = s.snapshot_ts
ORDER BY s.price_change_24h_pct DESC
LIMIT 20;

-- Rolling 24h average price using time-series table
SELECT
    c.symbol,
    p.price_ts,
    p.price_usd,
    AVG(p.price_usd) OVER (
        PARTITION BY c.coin_id
        ORDER BY p.price_ts
        ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
    ) AS rolling_24pt_avg_price
FROM fact_price_series p
JOIN dim_coin c ON c.coin_key = p.coin_key
WHERE c.symbol IN ('BTC', 'ETH')
ORDER BY c.symbol, p.price_ts;
