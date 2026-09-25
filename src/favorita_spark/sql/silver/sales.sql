-- one row per store × item × day; returns kept apart from units sold
SELECT
    date,
    store_nbr,
    item_nbr,
    sum(greatest(unit_sales, 0)) AS units,
    sum(greatest(-unit_sales, 0)) AS return_units,
    bool_or(onpromotion) AS on_promo  -- NULL when the flag is unknown
FROM bronze.train
WHERE date >= DATE '$slice_start'
GROUP BY date, store_nbr, item_nbr
