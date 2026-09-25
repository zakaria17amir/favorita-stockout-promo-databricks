WITH bounds AS (
    SELECT min(d) AS lo, max(d) AS hi
    FROM (SELECT date AS d FROM silver.sales UNION ALL SELECT date FROM silver.store_day) AS u
),
days AS (
    SELECT explode(sequence(lo, hi, INTERVAL 1 DAY)) AS date
    FROM bounds
)
SELECT
    CAST(date_format(d.date, 'yyyyMMdd') AS INT) AS date_key,
    d.date,
    year(d.date) AS year,
    quarter(d.date) AS quarter,
    month(d.date) AS month_num,
    date_format(d.date, 'MMM') AS month_name,
    year(d.date) * 100 + month(d.date) AS month_key,
    weekofyear(d.date) AS iso_week,
    extract(YEAROFWEEK FROM d.date) AS iso_year,
    extract(DAYOFWEEK_ISO FROM d.date) AS weekday_num,
    date_format(d.date, 'EEE') AS weekday_name,
    extract(DAYOFWEEK_ISO FROM d.date) >= 6 AS is_weekend,
    h.date IS NOT NULL AS is_national_holiday
FROM days AS d
LEFT JOIN silver.national_holidays AS h
    ON h.date = d.date
