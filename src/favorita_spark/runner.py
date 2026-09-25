"""Runs the SQL layers. Each .sql file is a single SELECT; the runner materialises it.

On Databricks every query becomes `CREATE OR REPLACE TABLE <layer>.<name>` (Delta, in the current
catalog). Locally (tests) it becomes a temp view named `<layer>__<name>`, because Windows Spark
cannot create databases without winutils; `localize` rewrites table references to match.
"""
import re
from importlib.resources import files
from string import Template

from pyspark.sql import SparkSession

from favorita_spark.config import Config

SILVER = ["sales", "store_day", "national_holidays", "stockout_series"]
GOLD = ["dim_date", "stg_store", "stg_item", "stg_store_day", "fact_sales", "fact_stockout_risk"]
LAYERS = {"silver": SILVER, "gold": GOLD}

_TABLE_REF = re.compile(r"\b(bronze|silver|gold)\.(\w+)\b")


def localize(sql: str) -> str:
    return _TABLE_REF.sub(r"\1__\2", sql)


def render(layer: str, name: str, cfg: Config) -> str:
    text = files("favorita_spark").joinpath("sql", layer, f"{name}.sql").read_text(encoding="utf-8")
    return Template(text).substitute(cfg.sql_params())


def build_sql_layer(spark: SparkSession, layer: str, cfg: Config, *, local: bool = False) -> None:
    for name in LAYERS[layer]:
        query = render(layer, name, cfg)
        if local:
            spark.sql(localize(query)).createOrReplaceTempView(f"{layer}__{name}")
        else:
            spark.sql(f"CREATE OR REPLACE TABLE {layer}.{name} AS\n{query}")
