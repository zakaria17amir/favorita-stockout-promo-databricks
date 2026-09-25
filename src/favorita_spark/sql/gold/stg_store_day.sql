SELECT CAST(date_format(date, 'yyyyMMdd') AS INT) AS date_key, store_nbr AS store_key, receipts
FROM silver.store_day
