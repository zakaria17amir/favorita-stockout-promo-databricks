# Stock-out & Promo on Databricks: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the PySpark repo as a Databricks Free Edition project. It ports Project 1's Favorita gold contract to Spark SQL (with parity tests), adds a Poisson + Benjamini–Hochberg stock-out run test and promo uplift/dip events with bootstrap CIs, renders Plotly charts, and reconciles with Project 1.

**Architecture:** Logic lives in `src/favorita_spark/`: `.sql` files (SELECT only) plus PySpark and numpy functions. A runner wraps each SQL file in `CREATE OR REPLACE TABLE` on Databricks, or `VIEW` in local tests, so tests never write files. The notebooks are thin runners. Two local scripts use DuckDB: `slice_raw.py` and `reconcile.py`.

**Tech Stack:** PySpark ≥ 3.5 (Databricks serverless / local Spark 4), Spark SQL, pandas, numpy, Plotly ≥ 5.24, DuckDB ≥ 1.1 (scripts), pytest ≥ 8, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-26-stockout-promo-databricks-design.md`

## Global Constraints

- Analysis window 2016-08-16 → 2017-08-15; raw slice starts 2016-06-21 (56-day burn-in).
- Lookback 28 days; λ threshold 3.0; partial day if receipts < 0.5 × trailing 28-day average; post-promo window 7 days.
- Runs: k ≤ 28 spine days; BH q = 0.05. Bootstrap: 1,000 resamples, seed 42, percentile 95% CI; families need ≥ 30 events.
- Default catalog `workspace`; schemas `bronze`, `silver`, `gold`; volumes `bronze.raw` and `gold.export`.
- SQL portability: date RANGE frames use `unix_date(date)` with integer offsets; no `FILTER` in windows (use `coalesce(sum(CASE…),0)`); no `IS [NOT] TRUE` (use `coalesce(x,false)`); `IN (subquery)` only in WHERE.
- Never commit data (`data/` is gitignored). Never push or rename the GitHub repo without the owner's OK.
- Python 3.11–3.13. Local tests use `local[1]` and an in-memory catalog.

## File structure

```
pyproject.toml
.github/workflows/ci.yml
src/favorita_spark/
  __init__.py
  config.py          Config dataclass + sql_params()
  runner.py          render(), build_sql_layer(), SILVER, GOLD
  bronze.py          RAW_SCHEMAS, read_raw(), load_bronze()
  sql/silver/{sales,store_day,national_holidays,stockout_series}.sql
  sql/gold/{dim_date,stg_store,stg_item,stg_store_day,fact_sales,fact_stockout_risk}.sql
  stockout.py        stockout_runs(), flag_bh(), dispersion(), weekly_flags()
  promo.py           promo_events(), bootstrap_median_ci(), family_summary()
  checks.py          CHECKS, run_checks()
  charts.py          five Plotly figure builders
scripts/slice_raw.py, scripts/reconcile.py
notebooks/00_setup … 07_export (.ipynb)
tests/conftest.py, tests/fixture_data.py (copied from Project 1)
tests/test_silver.py, test_fact_sales.py, test_stockout_risk.py, test_gold_dims.py,
      test_stockout_runs.py, test_promo.py, test_checks.py, test_charts.py,
      test_slice_raw.py, test_reconcile.py
```

---

### Task 1: Project scaffold + local Spark harness (spike-verified)

**Files:** Create `pyproject.toml`, `src/favorita_spark/__init__.py`, `src/favorita_spark/config.py`, `src/favorita_spark/bronze.py`, `tests/conftest.py`, `tests/fixture_data.py` (copied verbatim from `Flagship/pipeline/tests/fixture_data.py` with a one-line attribution), `tests/test_bronze.py`

**Interfaces — Produces:**
- `Config` (frozen dataclass) with fields `catalog="workspace"`, `raw_path="/Volumes/workspace/bronze/raw"`, `slice_start`, `window_start`, `window_end`, `lookback_days=28`, `min_expected_units=3.0`, `min_receipts_share=0.5`, `post_promo_days=7`, `max_run_days=28`, `fdr_q=0.05`, `bootstrap_resamples=1000`, `min_family_events=30`, `seed=42`, and `sql_params() -> dict[str, str]` (keys `stockout_from`, `lookback_days`, `min_expected_units`, `min_receipts_share`, `post_promo_days`).
- `bronze.RAW_SCHEMAS: dict[str, str]` (DDL strings), `read_raw(spark, raw_path, name) -> DataFrame`, `load_bronze(spark, cfg) -> dict[str, int]`.
- The pytest fixtures `spark`, `raw_dir`, `cfg` (fixture window 2016-01-01 → 2016-03-31) and `warehouse` (bronze registered as external CSV tables; silver and gold built as views; defined in Task 2).

- [x] Step 1: Spike (done 2026-09-26). Local Spark 4.2 on Java 23 works with `-Djava.security.manager=allow`.
  **`CREATE DATABASE` fails on Windows without winutils**, and **glob paths hang** (Hadoop NativeIO).
  Result: in local mode, `render(..., local=True)` rewrites `bronze.x`, `silver.x` and `gold.x` to temp-view names
  (`bronze__x`), and each layer is registered with `createOrReplaceTempView`. `read_raw` takes an exact file path
  (`Config.raw_ext`: `.csv.gz` on Databricks, `.csv` for the fixture). pandas is pinned below 3 (PySpark 4.2 warns on pandas 3).
- [x] Step 2: Write `tests/test_bronze.py`: `read_raw(spark, raw_dir, "train")` gives 5 typed columns; `onpromotion` stays NULL for store 2 in 2016 (91 rows); a malformed row raises under FAILFAST.
- [x] Step 3: Run it; it fails (module missing).
- [x] Step 4: Implement `config.py`, `bronze.py`, `conftest.py`.
- [x] Step 5: Run it; it passes. Commit `feat: project scaffold, config and bronze reader`.

### Task 2: Silver + gold contract SQL with Project 1 parity tests

**Files:** Create `src/favorita_spark/runner.py`, the 10 SQL files, `tests/test_silver.py`, `tests/test_fact_sales.py`, `tests/test_stockout_risk.py`, `tests/test_gold_dims.py`

**Interfaces — Produces:** `runner.SILVER = ["sales", "store_day", "national_holidays", "stockout_series"]`, `runner.GOLD = ["dim_date", "stg_store", "stg_item", "stg_store_day", "fact_sales", "fact_stockout_risk"]`, `render(layer, name, cfg) -> str`, and `build_sql_layer(spark, layer, cfg, *, as_view=False) -> None`. The table `silver.stockout_series(store_nbr, item_nbr, date, units, no_sale_row, full_day, lambda_units, history_days)`.

Parity tests assert Project 1's expected values exactly:
- `fact_sales` baselines 52/27, 50/26 and 46/24; `(False, False, None)` on 2016-01-20; no store 3 baselines; 91 unknown promo flags.
- `fact_stockout_risk == [(20160101, 1, 101, 4.82), (20160210, 1, 101, 5.0)]`; no store 3 flags.
- Silver: returns split out (0.0, 1.0); receipts 100; national holidays {2016-01-01, 2016-02-09}.
- Dims: `dim_date` flags 2016-01-01 as a holiday and 2016-01-02 as a weekend; `stg_item` 102 is perishable.

- [x] Step 1: Write the four test files. Step 2: run, fail. Step 3: implement the runner and the SQL (the port rules are in Global Constraints). Step 4: run, pass. Step 5: commit `feat: silver and gold contract SQL ported from Project 1 with parity tests`.

### Task 3: Stock-out runs, Benjamini–Hochberg, dispersion

**Files:** Create `src/favorita_spark/stockout.py`, `tests/test_stockout_runs.py`

**Interfaces — Produces:**
- `stockout_runs(series: DataFrame, cfg) -> DataFrame` returns the tested runs with columns `store_key, item_key, start_date_key, end_date_key, run_days, spine_days, calendar_days, lambda_units, p_value, expected_lost_units`.
- `flag_bh(runs: DataFrame, q: float) -> tuple[DataFrame, float | None]` adds `is_flagged` and returns the BH cut-off.
- `bh_summary(runs_flagged, cutoff) -> dict` with keys `tested_runs, flagged_runs, bh_cutoff, max_chance_flags`.
- `dispersion(series, cfg) -> DataFrame(store_nbr, item_nbr, mean_units, var_units, dispersion)`.
- `weekly_flags(runs_flagged) -> DataFrame(store_key, week_start, flagged_runs, lost_units)`.

Tests:
1. On the fixture, run (1, 101) starting 2016-02-10 has k = 1, λ = 5.0 and p = e^(−5). The 2016-03-01 partial day forms a run with k = 0, so it isn't tested. 2016-01-01 is tested, with λ = 4.82… and p = e^(−4.82…).
2. A hand-built series: a 3-day run at λ = 2 gives p = e^(−6), and a run of 30 days is excluded by `max_run_days`.
3. `flag_bh` on p = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216] with q = 0.05: the cut-off is 0.008 (ranks 1 and 2 pass: 0.001 ≤ 0.005 and 0.008 ≤ 0.010; rank 3: 0.039 > 0.015), so two are flagged.
4. `flag_bh` with nothing significant gives `(all False, None)`.
5. `dispersion`: a constant series gives variance 0 and dispersion 0.

- [x] Steps: write the tests → fail → implement → pass → commit `feat: Poisson zero-sale run test with Benjamini–Hochberg`.

### Task 4: Promo events + family bootstrap summary

**Files:** Create `src/favorita_spark/promo.py`, `tests/test_promo.py`

**Interfaces — Produces:**
- `promo_events(fact_sales, dim_date, stg_item, stg_store_day, cfg) -> DataFrame` with columns `store_key, item_key, family, start_date_key, end_date_key, promo_days, promo_units, baseline_units, uplift, post_units, post_expected_units, post_dip, touches_payday_or_holiday`.
- `bootstrap_median_ci(values, n, seed) -> tuple[float, float, float]`.
- `family_summary(events_pd: pandas.DataFrame, cfg) -> pandas.DataFrame` with columns `family, n_events, uplift_median, uplift_lo, uplift_hi, n_dip_events, dip_median, dip_lo, dip_hi`.

Tests:
1. On the fixture, there's one event (1, 102): 2016-01-10 → 01-12, 3 days, 18 units, baseline 52/27, uplift = 18 / (3 × 52/27) − 1.
2. Its post window is 01-13 → 01-19: 7 trading days × 2 units = 14, expected 7 × 52/27, and dip = 14 / (7 × 52/27) − 1.
3. `touches_payday_or_holiday` is False (01-10 to 01-12 contains no 15th, month-end or holiday).
4. The bootstrap CI brackets the median, and it's deterministic with the same seed.
5. `family_summary` drops families with fewer than `min_family_events` events.

- [x] Steps: tests → fail → implement → pass → commit `feat: promo events, uplift, post-promo dip and bootstrap family summary`.

### Task 5: Data checks + Plotly charts

**Files:** Create `src/favorita_spark/checks.py`, `src/favorita_spark/charts.py`, `tests/test_checks.py`, `tests/test_charts.py`

**Interfaces — Produces:**
- `run_checks(spark) -> dict[str, int]` (only failing checks). The check SQL covers key uniqueness for `fact_sales` and `fact_stockout_risk`, orphan store/item/date keys, and silver Σ units = gold Σ units.
- `charts.uplift_by_family(summary)`, `uplift_vs_dip(summary)`, `payday_check(events_pd)`, `stockout_heatmap(weekly_pd)` and `poisson_check(dispersion_pd)`, each returning `go.Figure`.
- `charts.save_all(figs: dict[str, go.Figure], out_dir) -> list[Path]`.

The charts follow the `dataviz` skill (loaded before this task).

- [x] Steps: tests (the fixture passes all checks; each chart builds from a small frame with the expected trace count and title) → fail → implement → pass → commit.

### Task 6: Scripts: slice_raw + reconcile

**Files:** Create `scripts/slice_raw.py`, `scripts/reconcile.py`, `tests/test_slice_raw.py`, `tests/test_reconcile.py`

**Interfaces — Produces:**
- `slice_raw(raw: Path, out: Path, start: date, end: date) -> dict[str, int]`: writes `train.csv.gz` and `transactions.csv.gz` date-filtered with `all_varchar` (raw text untouched), and `stores`, `items` and `holidays_events` whole.
- `reconcile(export_dir: Path, flagship_gold: Path, start: date, end: date) -> list[Check]`, where `Check = (name, value, passed, detail)`.
- `write_report(checks, path)`.
- A CLI for each.

Tests (DuckDB only, no Spark):
- The slice of the fixture keeps rows between 2016-01-01 and 2016-01-31, and the header and row text match the source lines.
- Reconcile on identical tiny Parquet sets passes everything. A changed baseline fails the baseline check, and a missing flag lowers the Jaccard similarity below 0.999.

- [x] Steps: tests → fail → implement → pass → commit.

### Task 7: Notebooks, CI, docs

**Files:** Create `notebooks/00_setup.ipynb` … `07_export.ipynb`, `.github/workflows/ci.yml`, `docs/decisions/ADR-001-free-edition-and-slice.md`, `docs/decisions/ADR-002-power-bi-link.md` (status Proposed, pending the day-one test); update `README.md`.

- The notebooks start with `sys.path.insert(0, os.path.abspath("../src"))`, then `USE CATALOG`, then call the library functions.
- 04 writes `silver.stockout_run_tested` and then flags from the table, because serverless has no `.cache()`.
- 06 runs `%pip install plotly>=5.24` and writes HTML to `/Volumes/<catalog>/gold/export/charts`.
- 07 runs `run_checks` first and raises on any failure, then writes Parquet per gold table to `/Volumes/<catalog>/gold/export/<table>`.
- CI: ubuntu-latest, `actions/setup-java@v4` (temurin 17), Python 3.12, `pip install -e ".[dev]"`, `pytest -q`.
- Validate each notebook's JSON with `json.load`. Commit.
