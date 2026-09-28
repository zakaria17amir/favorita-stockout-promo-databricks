"""Stock-out detection without ML: zero-sale runs that are too unlikely given the item's normal rate.

Poisson: an item that sells λ units a day has k zero days in a row with probability e^(−λk). But real
grocery demand varies far more than Poisson allows (variance ÷ mean ≈ 4 on Favorita), which makes zero
days commoner and Poisson over-flags. So the test uses a negative binomial with the same mean λ and the
item's own dispersion φ = variance ÷ mean, both from the previous 28 trading days:
P(zero day) = φ^(−λ/(φ−1)), and p = that to the power k. When φ ≤ 1 it is Poisson; the Poisson
p-value is kept alongside for comparison.

Millions of runs are tested at once, so the flags are chosen with Benjamini–Hochberg: of the runs
flagged, at most q (5%) are expected to be chance.
"""
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from favorita_spark.config import Config


def _date_key(col: str):
    return F.date_format(col, "yyyyMMdd").cast("int")


def stockout_runs(series: DataFrame, cfg: Config) -> DataFrame:
    """Tested zero-sale runs from silver.stockout_series, one row per run, with λ and p.

    A run is a maximal stretch of spine days without a sales row. Every run is followed by a
    sale because the spine ends at the pair's last sale, so open-ended gaps (delistings) never
    appear. A partial trading day inside a run doesn't count towards k and doesn't break the run.
    """
    pair = Window.partitionBy("store_nbr", "item_nbr").orderBy("date").rowsBetween(Window.unboundedPreceding, 0)
    zero_days = (
        series.withColumn("run_id", F.sum(F.when(F.col("no_sale_row"), 0).otherwise(1)).over(pair))
        .filter("no_sale_row")
    )
    runs = zero_days.groupBy("store_nbr", "item_nbr", "run_id").agg(
        F.min("date").alias("start_date"),
        F.max("date").alias("end_date"),
        F.sum(F.col("full_day").cast("int")).alias("run_days"),
        F.count("*").alias("spine_days"),
        # λ and history as they stood on the run's first day
        F.min_by("lambda_units", "date").alias("lambda_units"),
        F.min_by("var_units", "date").alias("var_units"),
        F.min_by("history_days", "date").alias("history_days"),
    )
    tested = runs.filter(
        F.col("start_date").between(F.lit(cfg.window_start), F.lit(cfg.window_end))
        & (F.col("history_days") == cfg.lookback_days)
        & (F.col("lambda_units") > 0)
        & (F.col("run_days") >= 1)
        & (F.col("spine_days") <= cfg.max_run_days)
    )
    lam, k = F.col("lambda_units"), F.col("run_days")
    phi = F.coalesce(F.col("var_units"), F.lit(0.0)) / lam
    # ln P(k zero days) = −kλ·ln φ/(φ−1) under the negative binomial; it tends to −kλ (Poisson) as φ → 1
    p_nb = F.exp(-k * lam * F.log(phi) / (phi - 1))
    p_poisson = F.exp(-lam * k)
    return tested.select(
        F.col("store_nbr").alias("store_key"),
        F.col("item_nbr").alias("item_key"),
        _date_key("start_date").alias("start_date_key"),
        _date_key("end_date").alias("end_date_key"),
        "run_days",
        "spine_days",
        (F.datediff("end_date", "start_date") + 1).alias("calendar_days"),
        "lambda_units",
        phi.alias("dispersion"),
        F.when(phi > 1, p_nb).otherwise(p_poisson).alias("p_value"),
        p_poisson.alias("p_poisson"),
        (F.col("lambda_units") * F.col("run_days")).alias("expected_lost_units"),
    )


def flag_bh(runs: DataFrame, q: float) -> tuple[DataFrame, float | None]:
    """Benjamini–Hochberg step-up: flag every p ≤ the largest p₍ᵢ₎ with p₍ᵢ₎ ≤ (i/m)·q."""
    m = runs.count()
    # ponytail: one global ranking = a single-partition window; fine for a few million runs.
    # If it grows past that, search the cut-off over approxQuantile buckets instead.
    ranked = runs.withColumn("_rank", F.row_number().over(Window.orderBy("p_value")))
    cutoff = ranked.filter(F.col("p_value") <= F.col("_rank") * q / m).agg(F.max("p_value")).first()[0] if m else None
    flagged = F.lit(False) if cutoff is None else F.col("p_value") <= F.lit(cutoff)
    return runs.withColumn("is_flagged", flagged), cutoff


def bh_summary(runs_flagged: DataFrame, cutoff: float | None) -> dict:
    """m tested, number flagged, the cut-off, and m·cut-off: at most this many flags are chance."""
    counts = runs_flagged.agg(F.count("*").alias("m"), F.sum(F.col("is_flagged").cast("int")).alias("n")).first()
    return {
        "tested_runs": counts.m,
        "flagged_runs": counts.n or 0,
        "bh_cutoff": cutoff,
        "max_chance_flags": counts.m * (cutoff or 0.0),
    }


def dispersion(series: DataFrame, cfg: Config) -> DataFrame:
    """Variance ÷ mean of daily units per store-item in the window. Poisson assumes 1;
    above 1 (overdispersion) means the run test flags too much."""
    in_window = series.filter(F.col("date").between(F.lit(cfg.window_start), F.lit(cfg.window_end)))
    return (
        in_window.groupBy("store_nbr", "item_nbr")
        .agg(F.mean("units").alias("mean_units"), F.var_samp("units").alias("var_units"))
        .filter("mean_units > 0")
        .withColumn("dispersion", F.col("var_units") / F.col("mean_units"))
    )


def weekly_stockout_rate(runs_flagged: DataFrame, series: DataFrame, stg_store: DataFrame, cfg: Config) -> DataFrame:
    """Share of tested item-days that sat inside a flagged run, per store and ISO week (Monday start).

    Dividing by item-days tested makes a small store comparable with a big one; a raw count of
    flagged runs mostly measures how many items a store carries. A store-week with no tested
    item-days has no row, so the heatmap leaves it blank rather than showing zero.
    ponytail: a run's days are credited to the week it starts in; runs are ≤ 28 days, so at worst
    part of one run lands a few weeks early. Explode runs to days if week-level precision matters.
    """
    week = lambda c: F.date_trunc("week", c).cast("date")  # noqa: E731
    tested = (
        series.filter(F.col("full_day") & F.col("date").between(F.lit(cfg.window_start), F.lit(cfg.window_end)))
        .groupBy(F.col("store_nbr").alias("store_key"), week(F.col("date")).alias("week_start"))
        .agg(F.count("*").alias("item_days"))
    )
    flagged = (
        runs_flagged.filter("is_flagged")
        .groupBy("store_key", week(F.to_date(F.col("start_date_key").cast("string"), "yyyyMMdd")).alias("week_start"))
        .agg(F.sum("run_days").alias("flagged_days"))
    )
    return (
        tested.join(flagged, ["store_key", "week_start"], "left")
        .fillna(0, ["flagged_days"])
        .join(stg_store.select("store_key", "city"), "store_key", "left")
        .withColumn("rate", F.col("flagged_days") / F.col("item_days"))
        .withColumn("week_start_key", _date_key("week_start"))  # Power BI relates this to its Date table
    )
