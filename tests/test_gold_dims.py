"""Same expectations as Project 1's pipeline/tests/test_gold_dims.py (DuckDB)."""
from datetime import date


def test_dim_date_covers_sales_and_receipts(sql):
    ((lo, hi, n),) = sql("SELECT min(date), max(date), count(*) FROM gold.dim_date")
    assert (lo, hi) == (date(2015, 1, 1), date(2016, 3, 31))
    assert n == (hi - lo).days + 1


def test_dim_date_attributes(sql):
    assert sql("SELECT date_key, month_key, weekday_num, weekday_name, is_weekend, is_national_holiday "
               "FROM gold.dim_date WHERE date = DATE'2016-01-02'") == [(20160102, 201601, 6, "Sat", True, False)]


def test_dim_date_holidays(sql):
    flags = dict(sql("SELECT date, is_national_holiday FROM gold.dim_date "
                     "WHERE date IN (DATE'2016-01-01', DATE'2016-02-08', DATE'2016-02-09')"))
    assert flags == {date(2016, 1, 1): True, date(2016, 2, 8): False, date(2016, 2, 9): True}
    assert sql("SELECT iso_year, iso_week FROM gold.dim_date WHERE date = DATE'2016-01-01'") == [(2015, 53)]


def test_opening_date_uses_full_receipt_history(sql):
    # store 1 traded from the first transactions date → unknown; store 3 opened 2016-01-01
    assert dict(sql("SELECT store_key, opening_date FROM gold.stg_store WHERE store_key IN (1, 2, 3)")) == {
        1: None, 2: date(2015, 6, 1), 3: date(2016, 1, 1)}


def test_stg_item_perishable_flag(sql):
    assert sql("SELECT family, is_perishable FROM gold.stg_item WHERE item_key = 102") == [("PRODUCE", True)]


def test_stg_store_day_keys(sql):
    assert sql("SELECT receipts FROM gold.stg_store_day WHERE store_key = 3 AND date_key = 20160115") == [(90,)]
