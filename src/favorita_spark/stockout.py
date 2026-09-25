"""Stock-out detection without ML: zero-sale runs that are too unlikely under a Poisson baseline.

If an item normally sells λ units a day, k full trading days in a row with no sale have
probability p = e^(−λk). Millions of runs are tested at once, so the flags are chosen with
Benjamini–Hochberg: of the runs flagged, at most q (5%) are expected to be chance.
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
        F.min_by("history_days", "date").alias("history_days"),
    )
    tested = runs.filter(
        F.col("start_date").between(F.lit(cfg.window_start), F.lit(cfg.window_end))
        & (F.col("history_days") == cfg.lookback_days)
        & (F.col("lambda_units") > 0)
        & (F.col("run_days") >= 1)
        & (F.col("spine_days") <= cfg.max_run_days)
    )
    return tested.select(
        F.col("store_nbr").alias("store_key"),
        F.col("item_nbr").alias("item_key"),
        _date_key("start_date").alias("start_date_key"),
        _date_key("end_date").alias("end_date_key"),
        "run_days",
        "spine_days",
        (F.datediff("end_date", "start_date") + 1).alias("calendar_days"),
        "lambda_units",
        F.exp(-F.col("lambda_units") * F.col("run_days")).alias("p_value"),
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


def weekly_flags(runs_flagged: DataFrame) -> DataFrame:
    """Flagged runs and estimated lost units per store and ISO week (Monday start), for the heatmap."""
    start = F.to_date(F.col("start_date_key").cast("string"), "yyyyMMdd")
    return (
        runs_flagged.filter("is_flagged")
        .groupBy("store_key", F.date_trunc("week", start).cast("date").alias("week_start"))
        .agg(F.count("*").alias("flagged_runs"), F.sum("expected_lost_units").alias("lost_units"))
    )
