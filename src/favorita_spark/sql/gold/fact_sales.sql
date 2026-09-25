WITH trading AS (
    SELECT
        store_nbr, date,
        count(*) OVER (PARTITION BY store_nbr ORDER BY unix_date(date)
                       RANGE BETWEEN $lookback_days PRECEDING AND 1 PRECEDING) AS trading_days
    FROM silver.store_day
    WHERE receipts > 0
),
windowed AS (
    SELECT
        date, store_nbr, item_nbr, units, return_units, on_promo,
        min(date) OVER (PARTITION BY store_nbr, item_nbr) AS first_sale,
        sum(CASE WHEN coalesce(on_promo, false) THEN 0 ELSE units END) OVER lookback AS base_units_sum,
        -- Spark has no FILTER in window aggregates, and sum over an empty frame is NULL
        coalesce(sum(CASE WHEN on_promo THEN 1 ELSE 0 END) OVER lookback, 0) AS promo_days_in_lookback,
        coalesce(sum(CASE WHEN on_promo THEN 1 ELSE 0 END) OVER recent, 0) AS promo_days_recent
    FROM silver.sales
    WINDOW
        lookback AS (PARTITION BY store_nbr, item_nbr ORDER BY unix_date(date)
                     RANGE BETWEEN $lookback_days PRECEDING AND 1 PRECEDING),
        recent AS (PARTITION BY store_nbr, item_nbr ORDER BY unix_date(date)
                   RANGE BETWEEN $post_promo_days PRECEDING AND 1 PRECEDING)
),
flagged AS (
    SELECT
        w.*,
        t.trading_days,
        NOT coalesce(w.on_promo, false) AND w.promo_days_recent > 0 AS post_promo_window,
        datediff(w.date, w.first_sale) >= $lookback_days AS has_full_history
    FROM windowed AS w
    LEFT JOIN trading AS t
        ON t.store_nbr = w.store_nbr AND t.date = w.date
)
SELECT
    CAST(date_format(date, 'yyyyMMdd') AS INT) AS date_key,
    store_nbr AS store_key,
    item_nbr AS item_key,
    units,
    return_units,
    on_promo,
    post_promo_window,
    CASE
        WHEN (coalesce(on_promo, false) OR post_promo_window) AND has_full_history
        -- days without a sales row count as zero units; promo days are excluded;
        -- the denominator counts trading days (store_day rows with receipts > 0);
        -- no store_day row for this date leaves the baseline NULL
        THEN coalesce(base_units_sum, 0) / nullif(trading_days - promo_days_in_lookback, 0)
    END AS baseline_units
FROM flagged
