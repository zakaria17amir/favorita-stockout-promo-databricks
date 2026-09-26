import math
from datetime import date, timedelta

import pytest

from favorita_spark.stockout import bh_summary, dispersion, flag_bh, stockout_runs, weekly_flags

SERIES_SCHEMA = ("store_nbr INT, item_nbr INT, date DATE, units DOUBLE, no_sale_row BOOLEAN, "
                 "full_day BOOLEAN, lambda_units DOUBLE, var_units DOUBLE, history_days BIGINT")


def series(spark, item, pattern, start=date(2016, 1, 1), lam=2.0, history=28, var=0.0):
    """pattern: 'S' = sale (2 units), '0' = zero on a full day, 'p' = zero on a partial day.
    var = trailing variance; ≤ λ means no overdispersion, so the test falls back to Poisson."""
    rows = [(1, item, start + timedelta(days=i), 2.0 if c == "S" else 0.0, c != "S", c != "p", lam, var, history)
            for i, c in enumerate(pattern)]
    return spark.createDataFrame(rows, SERIES_SCHEMA)


def by_item(df):
    return {r.item_key: r for r in df.collect()}


def test_fixture_runs_match_the_single_day_flags(warehouse, cfg):
    runs = {r.start_date_key: r for r in stockout_runs(warehouse.table("silver__stockout_series"), cfg).collect()}
    # the same two days Project 1 flags; the 2016-03-01 partial day has k = 0 so it is not tested
    assert set(runs) == {20160101, 20160210}
    jan, feb = runs[20160101], runs[20160210]
    assert (jan.store_key, jan.item_key, jan.run_days) == (1, 101, 1)
    assert jan.lambda_units == pytest.approx(27 * 5 / 28)
    assert jan.p_value == pytest.approx(math.exp(-27 * 5 / 28))
    assert (feb.run_days, feb.lambda_units, feb.expected_lost_units) == (1, 5.0, 5.0)
    assert feb.p_value == pytest.approx(math.exp(-5))


def test_run_probability_is_poisson_zero_run(spark, cfg):
    runs = by_item(stockout_runs(series(spark, 1, "S000S"), cfg))
    assert (runs[1].run_days, runs[1].spine_days, runs[1].calendar_days) == (3, 3, 3)
    assert runs[1].p_value == runs[1].p_poisson == pytest.approx(math.exp(-2.0 * 3))


def test_overdispersed_item_uses_negative_binomial(spark, cfg):
    # λ = 2, variance 6 → φ = 3. NB zero-day probability φ^(−λ/(φ−1)) = 3^(−1); three days → 3^(−3)
    (run,) = stockout_runs(series(spark, 1, "S000S", var=6.0), cfg).collect()
    assert run.dispersion == pytest.approx(3.0)
    assert run.p_value == pytest.approx(1 / 27)
    assert run.p_poisson == pytest.approx(math.exp(-6))  # Poisson would call this far less likely


def test_partial_day_neither_counts_nor_breaks_the_run(spark, cfg):
    runs = by_item(stockout_runs(series(spark, 1, "S0p0S"), cfg))
    assert (runs[1].run_days, runs[1].spine_days) == (2, 3)


def test_untestable_runs_are_dropped(spark, cfg):
    too_long = series(spark, 1, "S" + "0" * 30 + "S")
    before_window = series(spark, 2, "S00S", start=cfg.window_start - timedelta(days=2))
    short_history = series(spark, 3, "S00S", history=10)
    never_sells = series(spark, 4, "S00S", lam=0.0)
    df = too_long.unionAll(before_window).unionAll(short_history).unionAll(never_sells)
    assert stockout_runs(df, cfg).count() == 0


P_VALUES = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216]


def test_benjamini_hochberg_cutoff(spark):
    runs = spark.createDataFrame([(p,) for p in P_VALUES], "p_value DOUBLE")
    flagged, cutoff = flag_bh(runs, 0.05)
    # rank 2: 0.008 ≤ 2/10 × 0.05 = 0.010; rank 3: 0.039 > 0.015 and no later rank recovers
    assert cutoff == 0.008
    assert sorted(r.p_value for r in flagged.filter("is_flagged").collect()) == [0.001, 0.008]
    assert bh_summary(flagged, cutoff) == {
        "tested_runs": 10, "flagged_runs": 2, "bh_cutoff": 0.008, "max_chance_flags": pytest.approx(0.08)}


def test_benjamini_hochberg_nothing_significant(spark):
    runs = spark.createDataFrame([(0.5,), (0.9,)], "p_value DOUBLE")
    flagged, cutoff = flag_bh(runs, 0.05)
    assert cutoff is None and flagged.filter("is_flagged").count() == 0


def test_dispersion(spark, cfg):
    flat = series(spark, 1, "SSSS")                       # 2, 2, 2, 2 → variance 0
    lumpy = series(spark, 2, "S0S0")                      # 2, 0, 2, 0 → mean 1, var_samp 4/3
    rows = by_item(dispersion(flat.unionAll(lumpy), cfg).withColumnRenamed("item_nbr", "item_key"))
    assert rows[1].dispersion == 0
    assert rows[2].dispersion == pytest.approx(4 / 3)


def test_weekly_flags(spark):
    runs = spark.createDataFrame(
        [(1, 20160104, True, 3.0), (1, 20160107, True, 2.0), (1, 20160111, True, 1.0), (1, 20160105, False, 9.0)],
        "store_key INT, start_date_key INT, is_flagged BOOLEAN, expected_lost_units DOUBLE")
    rows = sorted(tuple(r) for r in weekly_flags(runs).collect())
    assert rows == [(1, date(2016, 1, 4), 2, 5.0), (1, date(2016, 1, 11), 1, 1.0)]


def test_dispersion_of_exactly_one_is_poisson(spark, cfg):
    (run,) = stockout_runs(series(spark, 1, "S00S", var=2.0), cfg).collect()  # φ = 2 / 2 = 1
    assert run.p_value == pytest.approx(math.exp(-4))
