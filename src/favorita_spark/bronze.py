"""Bronze: raw Favorita CSVs → typed tables. No business logic."""
from pyspark.sql import DataFrame, SparkSession

from favorita_spark.config import Config

RAW_SCHEMAS = {
    "train": "id BIGINT, date DATE, store_nbr INT, item_nbr INT, unit_sales DOUBLE, onpromotion BOOLEAN",
    "transactions": "date DATE, store_nbr INT, transactions INT",
    "stores": "store_nbr INT, city STRING, state STRING, type STRING, cluster INT",
    "items": "item_nbr INT, family STRING, class INT, perishable INT",
    "holidays_events": (
        "date DATE, type STRING, locale STRING, locale_name STRING, description STRING, transferred BOOLEAN"
    ),
}


def read_raw(spark: SparkSession, path: str, name: str) -> DataFrame:
    """Read one raw file with an explicit schema; a malformed row fails the read."""
    return spark.read.csv(path, schema=RAW_SCHEMAS[name], header=True, mode="FAILFAST")


def load_bronze(spark: SparkSession, cfg: Config) -> dict[str, int]:
    """Databricks: write each raw file to a bronze Delta table; returns row counts."""
    counts = {}
    for name in RAW_SCHEMAS:
        df = read_raw(spark, f"{cfg.raw_path}/{name}{cfg.raw_ext}", name)
        df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"bronze.{name}")
        counts[name] = spark.table(f"bronze.{name}").count()
    return counts
