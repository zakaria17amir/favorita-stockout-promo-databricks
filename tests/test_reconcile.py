from datetime import date

import duckdb

from reconcile import reconcile, write_report

START, END = date(2016, 8, 16), date(2017, 8, 15)
SALES = [(20160816, 1, 101, 5.0, 2.5), (20160817, 1, 101, 6.0, None), (20170815, 2, 102, 1.0, 1.0),
         (20160815, 1, 101, 99.0, 9.9)]  # the last row is burn-in, outside the window
RISK = [(20160901, 1, 101, 4.0), (20161001, 2, 102, 3.5)]


def write(root, sales, risk, as_dir):
    con = duckdb.connect()
    for table, rows, cols in (
        ("fact_sales", sales, "date_key INT, store_key INT, item_key INT, units DOUBLE, baseline_units DOUBLE"),
        ("fact_stockout_risk", risk, "date_key INT, store_key INT, item_key INT, expected_units DOUBLE"),
    ):
        con.execute(f"CREATE TABLE t ({cols})")
        con.executemany(f"INSERT INTO t VALUES ({', '.join('?' * len(rows[0]))})", rows)
        # Spark exports a folder of part files; Project 1 writes one file per table
        target = root / table / "part-0.parquet" if as_dir else root / f"{table}.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        con.execute(f"COPY t TO '{target.as_posix()}' (FORMAT parquet)")
        con.execute("DROP TABLE t")
    return root


def run(tmp_path, sales=SALES, risk=RISK):
    dbx = write(tmp_path / "dbx", sales, risk, as_dir=True)
    p1 = write(tmp_path / "p1", SALES, RISK, as_dir=False)
    return {c.name: c for c in reconcile(dbx, p1, START, END)}


def test_identical_tables_pass(tmp_path):
    checks = run(tmp_path)
    assert all(c.passed for c in checks.values()), checks
    assert checks["fact_sales rows"].value == "3 = 3"


def test_baseline_drift_fails(tmp_path):
    drifted = [(20160816, 1, 101, 5.0, 2.6)] + SALES[1:]
    checks = run(tmp_path, sales=drifted)
    assert not checks["baseline_units within 0.01"].passed
    assert checks["fact_sales Σ units"].passed


FLAGS = "stock-out flags ⊆ Project 1"
BASELINE_NULLS = "baseline NULLs only from sliced history"


def test_missing_flags_beyond_tolerance_fail(tmp_path):
    check = run(tmp_path, risk=RISK[:1])[FLAGS]
    assert not check.passed
    assert check.value == "Jaccard 0.5000; 0 only in Databricks, 1 only in Project 1"


def test_a_flag_only_databricks_has_is_a_bug(tmp_path):
    # the sliced history can only remove flags; one extra is a failure even when Jaccard is high
    many = [(20160901 + i % 28, 1 + i // 28, 101, 4.0) for i in range(1000)]
    dbx = write(tmp_path / "dbx", SALES, many + [(20170101, 9, 999, 4.0)], as_dir=True)  # λ well above 3: no tie
    p1 = write(tmp_path / "p1", SALES, many, as_dir=False)
    check = {c.name: c for c in reconcile(dbx, p1, START, END)}[FLAGS]
    assert not check.passed and "1 only in Databricks" in check.value


def test_a_baseline_only_databricks_has_is_a_bug(tmp_path):
    extra = [SALES[0], (20160817, 1, 101, 6.0, 1.5)] + SALES[2:]  # Project 1 has NULL here
    assert not run(tmp_path, sales=extra)[BASELINE_NULLS].passed


def test_baselines_databricks_lacks_are_explained(tmp_path):
    lacking = [(20160816, 1, 101, 5.0, None)] + SALES[1:]
    check = run(tmp_path, sales=lacking)[BASELINE_NULLS]
    assert check.value == "1 of 2 rows (50.000%); 0 where only Databricks has one"


def test_report_lists_every_check(tmp_path):
    checks = reconcile(write(tmp_path / "a", SALES, RISK, True), write(tmp_path / "b", SALES, RISK, False), START, END)
    report = tmp_path / "reconciliation.md"
    write_report(checks, report, START, END)
    text = report.read_text(encoding="utf-8")
    assert all(c.name in text for c in checks) and "PASS" in text


def test_empty_window_is_a_failure_not_a_crash(tmp_path):
    checks = run(tmp_path, sales=[SALES[-1]])  # only burn-in rows exported
    assert not checks["fact_sales rows"].passed


def test_threshold_ties_only_in_databricks_are_explained(tmp_path):
    # λ exactly 3.0 sits on the "λ ≥ 3" edge; whether an engine counts it depends on float rounding
    many = [(20160901 + i % 28, 1 + i // 28, 101, 4.0) for i in range(1000)]
    dbx = write(tmp_path / "dbx", SALES, many + [(20170131, 13, 1473479, 3.0)], as_dir=True)
    p1 = write(tmp_path / "p1", SALES, many, as_dir=False)
    check = {c.name: c for c in reconcile(dbx, p1, START, END)}[FLAGS]
    assert check.passed
    assert "1 only in Databricks (all at the λ = 3 threshold)" in check.value
