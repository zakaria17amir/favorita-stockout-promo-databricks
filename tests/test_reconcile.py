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


def test_missing_flag_lowers_jaccard(tmp_path):
    checks = run(tmp_path, risk=RISK[:1])
    assert not checks["stock-out flags Jaccard ≥ 0.999"].passed
    assert checks["stock-out flags Jaccard ≥ 0.999"].value == "0.5000"


def test_report_lists_every_check(tmp_path):
    checks = reconcile(write(tmp_path / "a", SALES, RISK, True), write(tmp_path / "b", SALES, RISK, False), START, END)
    report = tmp_path / "reconciliation.md"
    write_report(checks, report, START, END)
    text = report.read_text(encoding="utf-8")
    assert all(c.name in text for c in checks) and "PASS" in text


def test_empty_window_is_a_failure_not_a_crash(tmp_path):
    checks = run(tmp_path, sales=[SALES[-1]])  # only burn-in rows exported
    assert not checks["fact_sales rows"].passed
