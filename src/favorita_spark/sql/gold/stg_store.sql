SELECT
    s.store_nbr AS store_key,
    s.store_nbr,
    s.city,
    s.state,
    s.type AS store_type,
    s.cluster,
    o.opening_date
FROM bronze.stores AS s
JOIN (
    -- a store whose first receipt falls within 7 days of the data's first date was already
    -- trading when the data starts, so its true opening date is unknown, not that first receipt.
    SELECT store_nbr,
        CASE WHEN min(date) <= date_add((SELECT min(date) FROM bronze.transactions), 7)
            THEN NULL ELSE min(date) END AS opening_date
    FROM bronze.transactions
    GROUP BY store_nbr
) AS o
    ON o.store_nbr = s.store_nbr
