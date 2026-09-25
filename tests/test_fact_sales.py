"""Same expectations as Project 1's pipeline/tests/test_fact_sales.py (DuckDB)."""
import pytest


def row(sql, date_key, store=1, item=102):
    (r,) = sql("SELECT on_promo, post_promo_window, baseline_units FROM gold.fact_sales "
               f"WHERE date_key = {date_key} AND store_key = {store} AND item_key = {item}")
    return tuple(r)


def test_baseline_on_first_promo_day(sql):
    # 27 trading days before 2016-01-10 (28 calendar days minus the 12-25 closure);
    # 26 rows sell (12-20 is a genuine zero-sale trading day) × 2 units → 52 / 27
    on_promo, post, baseline = row(sql, 20160110)
    assert on_promo is True and post is False
    assert baseline == pytest.approx(52 / 27)


def test_baseline_excludes_promo_days(sql):
    # 27 trading days − 1 promo day; 25 non-promo rows × 2 → 50 / 26
    assert row(sql, 20160111)[2] == pytest.approx(50 / 26)


def test_post_promo_window(sql):
    on_promo, post, baseline = row(sql, 20160113)
    assert (on_promo, post) == (False, True)
    # 27 trading days − 3 promo days; 23 non-promo rows × 2 → 46 / 24
    assert baseline == pytest.approx(46 / 24)


def test_no_baseline_outside_promo_windows(sql):
    assert row(sql, 20160120) == (False, False, None)


def test_no_baseline_without_history(sql):
    # store 3 only sells from 2016-01-01: never enough history → always null
    assert sql("SELECT count(*) FROM gold.fact_sales WHERE store_key = 3 AND baseline_units IS NOT NULL") == [(0,)]


def test_unknown_promo_flag_stays_null(sql):
    assert sql("SELECT count(*) FROM gold.fact_sales WHERE store_key = 2 AND on_promo IS NULL") == [(91,)]
