"""Same expectations as Project 1's pipeline/tests/test_stockout.py (DuckDB)."""


def test_only_2016_gaps_are_flagged(sql):
    rows = sql("SELECT date_key, store_key, item_key, expected_units FROM gold.fact_stockout_risk ORDER BY 1")
    # 2015-12-15 gap is before the 2016-01-01 cut-off; slow sellers (λ < 3) never flag.
    # λ on 2016-01-01 = previous 28 trading days minus the 12-25 closure, including the
    # 2015-12-15 zero day → 27 × 5 / 28 = 4.82. 2016-03-01 is a partial trading day → not flagged.
    assert rows == [(20160101, 1, 101, 4.82), (20160210, 1, 101, 5.0)]


def test_delisting_is_not_flagged(sql):
    # store 3 stops selling after 2016-01-31 and never resumes → no flags
    assert sql("SELECT count(*) FROM gold.fact_stockout_risk WHERE store_key = 3") == [(0,)]
