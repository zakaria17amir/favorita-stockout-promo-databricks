"""Promo uplift: promotion days vs. the item's normal baseline, and the dip after the promotion.

An event is a run of consecutive promotion days for one store-item. Its baseline is Project 1's
28-day trailing non-promo average on the event's first day (gold.fact_sales.baseline_units).
"""
import numpy as np
import pandas as pd
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from favorita_spark.config import Config

_EVENT = ["store_key", "item_key", "event_id"]


def _date_key(col: str):
    return F.date_format(col, "yyyyMMdd").cast("int")


def promo_events(
    fact_sales: DataFrame, dim_date: DataFrame, stg_item: DataFrame, stg_store_day: DataFrame, cfg: Config
) -> DataFrame:
    days = dim_date.select("date_key", "date", "is_national_holiday")
    pair = Window.partitionBy("store_key", "item_key").orderBy("date")
    promo = (
        fact_sales.filter(F.col("on_promo"))
        .join(days, "date_key")
        # public-sector wages are paid on the 15th and the last day of the month
        .withColumn("payday", (F.dayofmonth("date") == 15) | (F.col("date") == F.last_day("date")))
        .withColumn(
            "event_id",
            F.sum(F.when(F.datediff("date", F.lag("date").over(pair)) == 1, 0).otherwise(1)).over(
                pair.rowsBetween(Window.unboundedPreceding, 0)),
        )
    )
    events = (
        promo.groupBy(*_EVENT)
        .agg(
            F.min("date").alias("start_date"),
            F.max("date").alias("end_date"),
            F.count("*").alias("promo_days"),
            F.sum("units").alias("promo_units"),
            F.min_by("baseline_units", "date").alias("baseline_units"),
            F.max((F.col("is_national_holiday") | F.col("payday")).cast("int")).alias("touches"),
        )
        # the next event is looked up before any filtering, so it always voids an overlapping dip
        .withColumn("next_start", F.lead("start_date").over(Window.partitionBy("store_key", "item_key").orderBy("start_date")))
        .filter((F.col("baseline_units") > 0) & F.col("start_date").between(F.lit(cfg.window_start), F.lit(cfg.window_end)))
        .withColumn("post_end", F.date_add("end_date", cfg.post_promo_days))
    )

    e = events.alias("e")
    in_post_window = lambda d: (d > F.col("e.end_date")) & (d <= F.col("e.post_end"))  # noqa: E731
    sales = fact_sales.join(days, "date_key").select("store_key", "item_key", "date", "units").alias("s")
    post_units = (
        e.join(sales, (F.col("s.store_key") == F.col("e.store_key")) & (F.col("s.item_key") == F.col("e.item_key"))
               & in_post_window(F.col("s.date")))
        .groupBy("e.store_key", "e.item_key", "e.event_id")
        .agg(F.sum("s.units").alias("post_units_raw"))
    )
    trading = stg_store_day.filter("receipts > 0").join(days, "date_key").select("store_key", "date").alias("t")
    post_days = (
        e.join(trading, (F.col("t.store_key") == F.col("e.store_key")) & in_post_window(F.col("t.date")))
        .groupBy("e.store_key", "e.item_key", "e.event_id")
        .agg(F.count("*").alias("post_trading_days"))
    )

    post_ok = (
        (F.col("next_start").isNull() | (F.col("next_start") > F.col("post_end")))  # no overlapping promo
        & (F.col("post_end") <= F.lit(cfg.window_end))                             # window inside the data
        & (F.col("post_trading_days") > 0)
    )
    post_expected = F.col("baseline_units") * F.col("post_trading_days")
    post_sold = F.coalesce(F.col("post_units_raw"), F.lit(0.0))  # days without a sales row sold nothing
    return (
        events.join(post_units, _EVENT, "left")
        .join(post_days, _EVENT, "left")
        .join(stg_item.select("item_key", "family"), "item_key", "left")
        .select(
            "store_key",
            "item_key",
            "family",
            _date_key("start_date").alias("start_date_key"),
            _date_key("end_date").alias("end_date_key"),
            "promo_days",
            "promo_units",
            "baseline_units",
            (F.col("promo_units") / (F.col("baseline_units") * F.col("promo_days")) - 1).alias("uplift"),
            F.when(post_ok, post_sold).alias("post_units"),
            F.when(post_ok, post_expected).alias("post_expected_units"),
            F.when(post_ok, post_sold / post_expected - 1).alias("post_dip"),
            # did it pay back? promotion + the week after, against what the baseline expects for both
            F.when(post_ok, (F.col("promo_units") + post_sold)
                   / (F.col("baseline_units") * F.col("promo_days") + post_expected) - 1).alias("net_lift"),
            (F.col("touches") == 1).alias("touches_payday_or_holiday"),
        )
    )


def bootstrap_median_ci(values, n: int, seed: int) -> tuple[float, float, float]:
    """Median with a percentile bootstrap 95% CI: resample the events n times, take the middle 95%."""
    v = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    boots = np.array([np.median(rng.choice(v, size=v.size)) for _ in range(n)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(np.median(v)), float(lo), float(hi)


def family_summary(events_pd: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Median uplift, post-promo dip and net lift per family, with bootstrap 95% CIs; small families are skipped.
    Dip and net lift exist only for events with a promotion-free week after, so they have their own counts."""
    nan3 = (float("nan"),) * 3
    rows = []
    for family, g in events_pd.groupby("family"):
        if len(g) < cfg.min_family_events:
            continue
        dips, nets = g["post_dip"].dropna(), g["net_lift"].dropna()
        ci = lambda v: (bootstrap_median_ci(v, cfg.bootstrap_resamples, cfg.seed)  # noqa: E731
                        if len(v) >= cfg.min_family_events else nan3)
        rows.append((family, len(g), *ci(g["uplift"]), len(dips), *ci(dips), len(nets), *ci(nets)))
    columns = ["family", "n_events", "uplift_median", "uplift_lo", "uplift_hi",
               "n_dip_events", "dip_median", "dip_lo", "dip_hi",
               "n_net_events", "net_median", "net_lo", "net_hi"]
    return pd.DataFrame(rows, columns=columns).sort_values("uplift_median", ascending=False, ignore_index=True)
