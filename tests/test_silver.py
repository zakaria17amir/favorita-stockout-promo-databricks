from datetime import date


def test_returns_are_split_from_units(sql):
    assert sql("SELECT units, return_units FROM silver.sales "
               "WHERE store_nbr = 2 AND item_nbr = 101 AND date = DATE'2016-01-05'") == [(0.0, 1.0)]


def test_store_day_receipts(sql):
    assert sql("SELECT receipts FROM silver.store_day WHERE store_nbr = 1 AND date = DATE'2016-02-10'") == [(100,)]


def test_store_day_starts_at_slice_start(sql, cfg):
    assert sql("SELECT min(date) FROM silver.store_day") == [(cfg.slice_start,)]


def test_national_holidays_respect_transfers(sql):
    days = {r[0] for r in sql("SELECT date FROM silver.national_holidays")}
    assert days == {date(2016, 1, 1), date(2016, 2, 9)}  # 02-08 transferred, 03-05 local
