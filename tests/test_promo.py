import math
from datetime import date, timedelta

import pandas as pd
import pytest

from favorita_spark.promo import bootstrap_median_ci, family_summary, promo_events


def fixture_events(warehouse, cfg):
    t = warehouse.table
    return promo_events(t("gold__fact_sales"), t("gold__dim_date"), t("gold__stg_item"), t("gold__stg_store_day"), cfg)


def test_fixture_event_uplift_and_dip(warehouse, cfg):
    (e,) = fixture_events(warehouse, cfg).collect()
    base = 52 / 27  # Project 1's baseline on the first promo day (2016-01-10)
    assert (e.store_key, e.item_key, e.family) == (1, 102, "PRODUCE")
    assert (e.start_date_key, e.end_date_key, e.promo_days, e.promo_units) == (20160110, 20160112, 3, 18.0)
    assert e.baseline_units == pytest.approx(base)
    assert e.uplift == pytest.approx(18 / (3 * base) - 1)
    # 2016-01-13..19: 7 trading days, 2 units each
    assert (e.post_units, e.post_expected_units) == (14.0, pytest.approx(7 * base))
    assert e.post_dip == pytest.approx(14 / (7 * base) - 1)
    # net: promo + following week vs. what the baseline expects for both → did it pay back?
    assert e.net_lift == pytest.approx((18 + 14) / (10 * base) - 1)
    assert e.touches_payday_or_holiday is False


def frames(spark, pattern, start, baseline=2.0):
    """'P' = promo day selling 6, '.' = normal day selling 2; one store, one DAIRY item, all days trading."""
    days = [start + timedelta(days=i) for i in range(len(pattern))]
    key = lambda d: int(d.strftime("%Y%m%d"))  # noqa: E731
    fact_sales = spark.createDataFrame(
        [(key(d), 1, 7, 6.0 if c == "P" else 2.0, c == "P", baseline) for d, c in zip(days, pattern)],
        "date_key INT, store_key INT, item_key INT, units DOUBLE, on_promo BOOLEAN, baseline_units DOUBLE")
    dim_date = spark.createDataFrame([(key(d), d, False) for d in days],
                                     "date_key INT, date DATE, is_national_holiday BOOLEAN")
    stg_item = spark.createDataFrame([(7, "DAIRY")], "item_key INT, family STRING")
    store_day = spark.createDataFrame([(key(d), 1, 100) for d in days], "date_key INT, store_key INT, receipts INT")
    return fact_sales, dim_date, stg_item, store_day


def events(spark, cfg, pattern, start, **kw):
    return sorted(promo_events(*frames(spark, pattern, start, **kw), cfg).collect(), key=lambda e: e.start_date_key)


def test_a_normal_day_splits_events_and_overlap_voids_the_dip(spark, cfg):
    first, second = events(spark, cfg, "..PP.PP.......", date(2016, 1, 1))
    assert (first.start_date_key, first.end_date_key, second.start_date_key) == (20160103, 20160104, 20160106)
    assert first.post_dip is None  # the next event starts inside its 7-day post window
    assert first.net_lift is None
    assert second.uplift == pytest.approx(12 / (2 * 2.0) - 1)
    assert second.post_dip == pytest.approx(0.0)  # 01-08..14 sell the normal 2/day


def test_payday_is_flagged(spark, cfg):
    (e,) = events(spark, cfg, ".PP........", date(2016, 1, 14))  # promo on the 15th and 16th
    assert e.touches_payday_or_holiday is True


def test_post_window_past_the_data_has_no_dip(spark, cfg):
    (e,) = events(spark, cfg, ".PP...", date(2016, 3, 27))  # ends 03-29; +7 days > window end 03-31
    assert e.post_dip is None and e.uplift == pytest.approx(2.0)


def test_events_without_baseline_are_dropped(spark, cfg):
    assert events(spark, cfg, ".PP.", date(2016, 1, 1), baseline=None) == []


def test_bootstrap_ci_brackets_the_median_and_is_repeatable():
    values = list(range(1, 102))
    median, lo, hi = bootstrap_median_ci(values, 1000, 42)
    assert median == 51 and lo < 51 < hi
    assert bootstrap_median_ci(values, 1000, 42) == (median, lo, hi)


def test_family_summary_needs_enough_events(cfg):
    df = pd.DataFrame({
        "family": ["A"] * 40 + ["B"] * 10,
        "uplift": [0.5] * 40 + [9.0] * 10,
        "post_dip": [-0.1] * 35 + [None] * 5 + [0.0] * 10,
        "net_lift": [0.2] * 35 + [None] * 5 + [1.0] * 10,
    })
    out = family_summary(df, cfg)
    assert out["family"].tolist() == ["A"]
    row = out.iloc[0]
    assert (row.n_events, row.uplift_median, row.uplift_lo, row.uplift_hi) == (40, 0.5, 0.5, 0.5)
    assert (row.n_dip_events, row.dip_median) == (35, pytest.approx(-0.1))
    assert not math.isnan(row.dip_lo)
    assert (row.n_net_events, row.net_median, row.net_lo, row.net_hi) == (35, 0.2, 0.2, 0.2)
