"""Reconcile the Databricks contract tables with Project 1's DuckDB gold over the analysis window.

Pass criteria (spec 4.3): equal fact_sales rows and Σ units; baselines within 0.01 where both exist.
The slice starts later than Project 1's history, so an item that reappears after a long silence gets
a later first sale here. That can only REMOVE baselines and stock-out flags, never add them. So those
two checks are directional: anything only Databricks has is a bug; what it lacks must stay small
(baseline NULL mismatches ≤ 0.5%, flag Jaccard ≥ 0.995). One exception: a flag whose λ is exactly the
λ ≥ 3 threshold. Whether a float average of exactly 3 lands on 3.0 or 2.9999999999999996 depends on the
engine's summation order, so such a tie may appear on either side; it is reported, not failed.

    python scripts/reconcile.py --export data/export --flagship ../Flagship/data/full/gold
"""
import argparse
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb

MIN_EXPECTED_UNITS = 3.0  # the contract's λ threshold (Project 1 and fact_stockout_risk.sql)


@dataclass(frozen=True)
class Check:
    name: str
    value: str
    passed: bool
    detail: str


def _parquet(root: Path, table: str) -> str:
    """Spark exports a folder of part files; Project 1 writes one file per table."""
    folder = Path(root) / table
    path = folder / "*.parquet" if folder.is_dir() else Path(root) / f"{table}.parquet"
    return f"read_parquet('{path.as_posix()}')"


def reconcile(export_dir: Path, flagship_gold: Path, start: date, end: date) -> list[Check]:
    con = duckdb.connect()
    k0, k1 = int(start.strftime("%Y%m%d")), int(end.strftime("%Y%m%d"))
    for alias, root in (("dbx", export_dir), ("p1", flagship_gold)):
        for table in ("fact_sales", "fact_stockout_risk"):
            con.execute(f"CREATE VIEW {alias}_{table} AS SELECT * FROM {_parquet(root, table)} "
                        f"WHERE date_key BETWEEN {k0} AND {k1}")
    one = lambda q: con.execute(q).fetchone()  # noqa: E731

    rows_d, units_d = one("SELECT count(*), coalesce(sum(units), 0) FROM dbx_fact_sales")
    rows_p, units_p = one("SELECT count(*), coalesce(sum(units), 0) FROM p1_fact_sales")
    drift, mismatched, dbx_only_baselines, with_baseline = one("""
        SELECT
            count(*) FILTER (WHERE abs(d.baseline_units - p.baseline_units) > 0.01),
            count(*) FILTER (WHERE (d.baseline_units IS NULL) <> (p.baseline_units IS NULL)),
            count(*) FILTER (WHERE d.baseline_units IS NOT NULL AND p.baseline_units IS NULL),
            count(*) FILTER (WHERE d.baseline_units IS NOT NULL OR p.baseline_units IS NOT NULL)
        FROM dbx_fact_sales AS d
        JOIN p1_fact_sales AS p USING (date_key, store_key, item_key)""")
    both, dbx_only_flags, dbx_only_ties, union = one(f"""
        SELECT count(*) FILTER (WHERE d.date_key IS NOT NULL AND p.date_key IS NOT NULL),
               count(*) FILTER (WHERE p.date_key IS NULL),
               count(*) FILTER (WHERE p.date_key IS NULL AND abs(d.expected_units - {MIN_EXPECTED_UNITS}) < 1e-9),
               count(*)
        FROM dbx_fact_stockout_risk AS d
        FULL JOIN p1_fact_stockout_risk AS p USING (date_key, store_key, item_key)""")
    null_share = mismatched / with_baseline if with_baseline else 0.0
    jaccard = both / union if union else 1.0
    return [
        Check("fact_sales rows", f"{rows_d:,} = {rows_p:,}" if rows_d == rows_p else f"{rows_d:,} ≠ {rows_p:,}",
              rows_d == rows_p and rows_d > 0, "Databricks vs Project 1, analysis window only"),
        Check("fact_sales Σ units", f"{units_d:,.2f} vs {units_p:,.2f}",
              abs(units_d - units_p) <= 1e-6 * max(1.0, abs(units_p)), "relative tolerance 1e-6"),
        Check("baseline_units within 0.01", f"{drift:,} rows differ", drift == 0,
              "rows where both tables have a baseline"),
        Check("baseline NULLs only from sliced history",
              f"{mismatched:,} of {with_baseline:,} rows ({null_share:.3%}); "
              f"{dbx_only_baselines:,} where only Databricks has one",
              dbx_only_baselines == 0 and null_share <= 0.005,
              "Databricks may lack a baseline (later first sale), never add one; ≤ 0.5%"),
        Check("stock-out flags ⊆ Project 1",
              f"Jaccard {jaccard:.4f}; {dbx_only_flags:,} only in Databricks"
              + (f" (all at the λ = {MIN_EXPECTED_UNITS:g} threshold)" if dbx_only_flags and dbx_only_flags == dbx_only_ties else "")
              + f", {union - both - dbx_only_flags:,} only in Project 1",
              dbx_only_flags == dbx_only_ties and jaccard >= 0.995,
              "Databricks may miss flags (shorter spine history), never add one except a λ-exactly-at-threshold tie; "
              "Jaccard ≥ 0.995"),
    ]


def write_report(checks: list[Check], path: Path, start: date, end: date) -> None:
    lines = [
        "# Reconciliation: Databricks vs Project 1",
        "",
        f"Contract tables compared over the analysis window {start} → {end}. Generated by `scripts/reconcile.py`.",
        "",
        "| Check | Result | Status | Note |",
        "|---|---|---|---|",
        *(f"| {c.name} | {c.value} | {'PASS' if c.passed else 'FAIL'} | {c.detail} |" for c in checks),
        "",
    ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--export", type=Path, default=Path("data/export"), help="Parquet from notebook 07")
    parser.add_argument("--flagship", type=Path, required=True, help="Project 1 data/full/gold")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2016, 8, 16))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2017, 8, 15))
    parser.add_argument("--out", type=Path, default=Path("docs/reconciliation.md"))
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # check names use Σ and ≥; Windows consoles default to cp1252
    checks = reconcile(args.export, args.flagship, args.start, args.end)
    write_report(checks, args.out, args.start, args.end)
    for c in checks:
        print(f"{'PASS' if c.passed else 'FAIL'}  {c.name}: {c.value}")
    sys.exit(0 if all(c.passed for c in checks) else 1)


if __name__ == "__main__":
    main()
