"""Data checks that must pass before the gold tables are exported. Each query returns one
number: the count of violations (0 = pass)."""
from pyspark.sql import SparkSession

from favorita_spark.runner import localize

CHECKS = {
    "fact_sales_duplicate_keys":
        "SELECT count(*) - count(DISTINCT date_key, store_key, item_key) FROM gold.fact_sales",
    "fact_stockout_risk_duplicate_keys":
        "SELECT count(*) - count(DISTINCT date_key, store_key, item_key) FROM gold.fact_stockout_risk",
    "fact_sales_orphan_store":
        "SELECT count(*) FROM gold.fact_sales AS f LEFT ANTI JOIN gold.stg_store AS s ON s.store_key = f.store_key",
    "fact_sales_orphan_item":
        "SELECT count(*) FROM gold.fact_sales AS f LEFT ANTI JOIN gold.stg_item AS i ON i.item_key = f.item_key",
    "fact_sales_orphan_date":
        "SELECT count(*) FROM gold.fact_sales AS f LEFT ANTI JOIN gold.dim_date AS d ON d.date_key = f.date_key",
    "fact_stockout_risk_orphan_date":
        "SELECT count(*) FROM gold.fact_stockout_risk AS f "
        "LEFT ANTI JOIN gold.dim_date AS d ON d.date_key = f.date_key",
    "units_silver_vs_gold":
        "SELECT CASE WHEN abs((SELECT sum(units) FROM silver.sales) - (SELECT sum(units) FROM gold.fact_sales))"
        " > 1e-6 THEN 1 ELSE 0 END",
}


def run_checks(spark: SparkSession, checks: dict[str, str] = CHECKS, *, local: bool = False) -> dict[str, int]:
    """Only the failing checks, name → violation count."""
    results = {name: spark.sql(localize(q) if local else q).first()[0] for name, q in checks.items()}
    return {name: n for name, n in results.items() if n}
