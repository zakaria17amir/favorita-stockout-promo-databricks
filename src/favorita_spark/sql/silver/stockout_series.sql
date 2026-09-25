-- Daily series behind both stock-out tables: store-item pairs that could reach λ ≥ threshold,
-- on the store's trading days (receipts > 0) between the pair's first and last sale.
-- Days without a sales row count as zero units.
WITH pairs AS (
    SELECT store_nbr, item_nbr, min(date) AS first_sale, max(date) AS last_sale
    FROM silver.sales
    WHERE date >= date_sub(DATE '$stockout_from', 2 * $lookback_days)
    GROUP BY store_nbr, item_nbr
    HAVING sum(units) >= $min_expected_units * $lookback_days
),
spine AS (
    SELECT p.store_nbr, p.item_nbr, d.date
    FROM pairs AS p
    JOIN silver.store_day AS d
        ON d.store_nbr = p.store_nbr
       AND d.receipts > 0
       AND d.date BETWEEN p.first_sale AND p.last_sale
),
full_days AS (
    -- a partial trading day (e.g. a store that closed early) is not evidence of a stock-out
    SELECT store_nbr, date,
           receipts >= $min_receipts_share * avg(receipts) OVER (
               PARTITION BY store_nbr ORDER BY unix_date(date)
               RANGE BETWEEN $lookback_days PRECEDING AND 1 PRECEDING) AS full_day
    FROM silver.store_day
    WHERE receipts > 0
)
SELECT
    sp.store_nbr,
    sp.item_nbr,
    sp.date,
    coalesce(s.units, 0) AS units,
    s.store_nbr IS NULL AS no_sale_row,
    coalesce(f.full_day, false) AS full_day,
    avg(coalesce(s.units, 0)) OVER prev AS lambda_units,
    count(*) OVER prev AS history_days
FROM spine AS sp
JOIN full_days AS f
    ON f.store_nbr = sp.store_nbr AND f.date = sp.date
LEFT JOIN silver.sales AS s
    ON s.store_nbr = sp.store_nbr AND s.item_nbr = sp.item_nbr AND s.date = sp.date
WINDOW prev AS (PARTITION BY sp.store_nbr, sp.item_nbr ORDER BY sp.date
                ROWS BETWEEN $lookback_days PRECEDING AND 1 PRECEDING)
