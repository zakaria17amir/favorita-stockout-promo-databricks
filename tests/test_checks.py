from favorita_spark.checks import CHECKS, run_checks


def test_fixture_passes_every_check(warehouse):
    assert run_checks(warehouse, local=True) == {}


def test_only_failing_checks_are_returned(warehouse):
    assert run_checks(warehouse, {"ok": "SELECT 0", "broken": "SELECT 3"}) == {"broken": 3}


def test_every_contract_fact_is_checked():
    assert {"fact_sales_duplicate_keys", "fact_stockout_risk_duplicate_keys", "units_silver_vs_gold"} <= set(CHECKS)
