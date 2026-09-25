-- Project 1's single-day rule: a zero-sale full trading day with λ ≥ threshold (so a zero has
-- Poisson probability ≤ 5%) that resumes selling within the lookback window.
WITH scored AS (
    SELECT
        *,
        coalesce(sum(CASE WHEN units > 0 THEN 1 ELSE 0 END) OVER (
            PARTITION BY store_nbr, item_nbr ORDER BY unix_date(date)
            RANGE BETWEEN 1 FOLLOWING AND $lookback_days FOLLOWING), 0) AS future_sales
    FROM silver.stockout_series
)
SELECT
    CAST(date_format(date, 'yyyyMMdd') AS INT) AS date_key,
    store_nbr AS store_key,
    item_nbr AS item_key,
    round(lambda_units, 2) AS expected_units
FROM scored
WHERE date >= DATE '$stockout_from'
  AND full_day
  AND no_sale_row
  AND history_days = $lookback_days
  AND lambda_units >= $min_expected_units
  AND future_sales > 0
