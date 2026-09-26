# Stock-out & promo analysis on Databricks: design

- Date: 2026-09-26
- Status: Section 1 approved live. Sections 2–4 were written while the owner was away and still need their review.
- Repo: `zakaria17amir/Sales-Menu-Data-Analysis-Using-PySpark-Apache-Spark`, to be renamed
  `favorita-stockout-promo-databricks`. GitHub redirects the old URL, so CV links keep working.
- Feeds: Project 1, the Store Performance Cockpit (`store-performance-fabric`).

## 1. Goal and scope

Process a 12-month slice of Favorita on **Databricks Free Edition** through bronze → silver → gold,
using both PySpark and SQL, and answer two questions with statistics that can be explained in one sentence:

1. **Stock-outs, without machine learning:** which zero-sale runs are too unlikely given the item's
   normal daily rate? The model is a Poisson baseline, corrected for running millions of tests at once.
2. **Promo uplift:** how much do promotions lift units above the item's normal baseline, and how
   much do sales dip in the week after a promotion?

Results are shown as interactive Plotly charts and feed Project 1 in two ways:

- **Contract tables:** the same grain and columns as Project 1's gold tables for the window. They are
  reconciled against Project 1's DuckDB output, which proves the architecture claim that "any producer can replace DuckDB".
- **New analysis tables:** `fact_stockout_run`, `fact_promo_event` and `promo_family_summary`. They
  appear in Power BI as an extra deep-dive page.

Out of scope: forecasting and ML models,
difference-in-differences promo analysis (the check chart exposes the bias it would fix), and
scheduled jobs.

## 2. Architecture and data flow (approved)

| Item | Decision |
|---|---|
| Analysis window | 2016-08-16 → 2017-08-15 (the last 12 months of Favorita) |
| Raw slice | 2016-06-21 → 2017-08-15: the window plus a 56-day burn-in, so trailing windows and the stock-out spine are complete on day one |
| Ingest | `scripts/slice_raw.py` (DuckDB) date-filters `train.csv` into a gzipped CSV (raw text untouched). The small files, including `transactions`, stay whole so store opening dates use full history, and `silver.store_day` filters to the slice. Upload with `databricks fs cp` or the volume UI (5 GB per file). Real run: 42.8M rows, 297 MB |
| Catalog | Configurable, default `workspace` (Free Edition's default catalog); schemas `bronze`, `silver`, `gold`; volume `bronze.raw` |
| bronze | PySpark: typed CSV read → Delta. No logic |
| silver, gold contract | Spark SQL files ported from Project 1's DuckDB SQL (`sales`, `store_day`, `national_holidays`, `dim_date`, `stg_store`, `stg_item`, `stg_store_day`, `fact_sales`, `fact_stockout_risk`). Project 1's stock-out spine moves into `silver.stockout_series`, shared by `fact_stockout_risk` and the run test |
| gold, new | PySpark: `fact_stockout_run`, `fact_promo_event`. pandas/numpy: `promo_family_summary` |
| Code shape | Logic in `src/favorita_spark/` (functions from DataFrame to DataFrame, plus `.sql` files). The notebooks are thin runners that import it through a Databricks Git folder |
| Link to Project 1 | Day-one test: Power BI Databricks connector plus a personal access token against the SQL warehouse. Fallback: export Parquet and upload it to OneLake. The result goes in ADR-002 |

### SQL portability rules (DuckDB → Spark SQL)

- Date `RANGE` frames order by `unix_date(date)` with integer offsets (`RANGE BETWEEN 28 PRECEDING AND 1 PRECEDING`).
- `count(*) FILTER (WHERE x) OVER w` becomes `coalesce(sum(CASE WHEN x THEN 1 ELSE 0 END) OVER w, 0)`,
  because Spark has no `FILTER` in window aggregates and `sum` over an empty frame is NULL where DuckDB's `count` is 0.
- `strftime(d, '%Y%m%d')` becomes `date_format(d, 'yyyyMMdd')`. DuckDB's `datediff('day', a, b)` becomes Spark's `datediff(b, a)`.
- The SQL files contain only a `SELECT`. The runner wraps each one in `CREATE OR REPLACE TABLE … AS` on
  Databricks. In local tests it registers a temp view named `<layer>__<name>` and rewrites table references
  to match. Windows Spark can't `CREATE DATABASE` without winutils, and glob paths hang, so `read_raw` takes exact paths.
- Parameters use `string.Template` (`$lookback_days`), the same as Project 1.

## 3. Statistics

### 3.1 Stock-out runs (`gold.fact_stockout_run`)

This reuses the Project 1 series: store-item pairs that could reach λ ≥ 3, on a spine of the store's
trading days (receipts > 0) between the pair's first and last sale in the slice. Days without a sales row count as zero.

- **Run:** a maximal sequence of consecutive spine days with no sales row. A sale ends the run.
- **k:** the number of *full* trading days in the run (receipts ≥ 50% of the store's trailing 28-day
  average). A partial day inside a run doesn't count as evidence, but it doesn't break the run either.
- **λ:** the average units over the 28 spine rows before the run starts. This is the same definition as
  `expected_units` in `fact_stockout_risk`, so a one-day run has the same λ in both tables.
- **p-value (revised 2026-09-26, ADR-003):** negative binomial with mean λ and dispersion φ = variance ÷ mean,
  both over the same 28 spine rows: p = φ^(−λk/(φ−1)). When φ ≤ 1 this is Poisson, p = e^(−λk), and `p_poisson`
  is kept for comparison. The original Poisson-only design flagged 38% of runs on real data because the median φ was 4.4.
- **Tested runs:** runs that start inside the analysis window, have 28 rows of history, have λ > 0 and k ≥ 1,
  **resume** (a sale follows the run), and have k ≤ 28 (longer gaps look like delisting, which matches
  Project 1's "resumes within 28 days" rule).
- **Multiple testing:** Benjamini–Hochberg at q = 0.05 across all tested runs. Rank p ascending, find the
  largest rank i with p₍ᵢ₎ ≤ (i/m)·q, and flag every run with p ≤ p₍ᵢ₎. In words: *of the runs we flag,
  we expect at most 5% to be chance.*
- **Reported alongside:** m (tested runs), the number flagged, the BH cut-off t, and m·t, the upper
  bound on how many flags chance alone would produce.
- **Columns:** `store_key, item_key, start_date_key, end_date_key, run_days (k), calendar_days,
  lambda_units, p_value, is_flagged, expected_lost_units (= λ·k)`. All tested runs are kept, and the model filters `is_flagged`.
- **Overdispersion chart:** variance ÷ mean of daily units per store-item over the window. A value above 1 means
  more variation than Poisson assumes (overdispersion), which inflates flags. The chart and the README state this, and
  the chart explains why the run test uses a negative binomial.

`ponytail:` BH needs one global ranking, so it runs as a single-partition window over the run table. That's fine for
a few million rows. Switch to an approximate quantile if it ever grows past that.

### 3.2 Promo events (`gold.fact_promo_event`)

Built on the contract `fact_sales` (on_promo, baseline_units):

- **Event:** consecutive calendar days with `on_promo = true` for one store-item. A gap of more than one day starts a new event.
- **Baseline:** `baseline_units` on the event's first day (Project 1's definition: the 28-day trailing
  non-promo average over trading days). Events without a baseline > 0 are dropped.
- **Uplift:** Σ units on event days ÷ (baseline × event days) − 1.
- **Post-promo dip:** the 7 calendar days after the event ends. Missing sales rows count as zero, expected =
  baseline × trading days in that window, and dip = actual ÷ expected − 1. It's NULL when another promo event for the
  pair starts inside those 7 days or the window runs past the end of the data. Real data: about 1 in 6 events has a clean week; the rule is kept because overlapping weeks mix the dip with the next lift.
- **Holiday/payday flag:** `touches_payday_or_holiday` is true if any event day is a national holiday or a public-sector
  payday (the 15th or the last day of the month).
- Only events that start inside the analysis window are kept.

### 3.3 Family summary (`gold.promo_family_summary`)

For each item family with at least 30 events: `n_events`, the median uplift, and a bootstrap 95% CI
(1,000 resamples of events, seed 42, percentile method), plus the same for the dip. It's computed in numpy
from the event table, which is small enough to collect.

## 4. Delivery

### 4.1 Plotly charts (`src/favorita_spark/charts.py`)

Each chart is a function that takes pandas and returns a `go.Figure`, built with the `dataviz` skill's rules.
Each title states the chart's finding, computed from the data:

1. **Uplift by family:** a dot plot with 95% CI whiskers, sorted by the median.
2. **Promo payback (revised 2026-09-26):** net lift per family (promotion + the week after vs. the baseline for
   both), a ranked dot plot with 95% CI, coloured by whether the CI clears zero. It replaced an uplift-vs-dip scatter
   whose outliers squashed the other families and which never answered its own question.
3. **Holiday/payday check:** median uplift for events that touch a holiday or payday vs. those that don't, per family.
4. **Stock-out heatmap (revised 2026-09-26):** store × ISO week, coloured by the stock-out *rate* (flagged zero days ÷
   item-days tested; raw counts mostly measured store size), stores worst first with their city, colour capped at the
   95th percentile, untested weeks blank, and each store's yearly rate as a bar alongside.
5. **Poisson check:** a histogram of variance ÷ mean, with a reference line at 1.

Notebook 06 displays them and writes standalone HTML to `docs/charts/` for GitHub Pages.

### 4.2 Notebooks (`notebooks/`, `.ipynb`, rendered by GitHub)

`00_setup` (catalog, schemas, volume, connector checklist) · `01_bronze` · `02_silver` ·
`03_gold_contract` · `04_stockout_runs` · `05_promo_events` · `06_charts` · `07_export`
(Parquet to the volume, for the reconciliation and the OneLake fallback).

### 4.3 Reconciliation (`scripts/reconcile.py`, local DuckDB)

This compares the exported Databricks contract tables with Project 1's `data/full/gold/*.parquet` over
the analysis window. Pass criteria:

- `fact_sales`: row count and Σ units are equal.
- `baseline_units`: |Δ| ≤ 0.01 wherever both are non-null.
- **Directional checks.** The slice starts later than Project 1's history, so an item that reappears after a
  long silence gets a later first sale. That can only *remove* baselines and stock-out flags, never add them
  (both tables are subsets of Project 1's by construction). So a baseline or flag that only Databricks has is a
  failure. What Databricks lacks must stay small: baseline NULL mismatches ≤ 0.5%, flag Jaccard ≥ 0.995.
- The original fixed tolerances (0.1% / 0.999) were replaced after a real-data smoke run on 3 stores measured
  0.153% / 0.9987, all in the expected direction.

The script writes `docs/reconciliation.md`.

### 4.4 Testing

- **Parity tests:** Project 1's synthetic fixture (`fixture_data.py`, copied with attribution) runs through
  the Spark port, and the tests assert **the same expected values** as Project 1's DuckDB tests.
  The window config is set to the fixture's dates (`stockout_from = 2016-01-01`).
- **Statistics tests:** small hand-built series with known runs, p-values, BH cut-offs, event uplifts, and
  a bootstrap CI that brackets the true median.
- `pytest` runs locally with `local[1]` Spark and an in-memory catalog. CI runs the same tests on Ubuntu with
  Java 17 in GitHub Actions.

### 4.5 Error handling

- `bronze` reads with an explicit schema and `mode=FAILFAST`, so malformed raw rows fail loudly.
- `07_export` runs data checks first: key uniqueness per gold grain, no orphan keys, silver Σ units = gold Σ units.
  If a check fails, it raises before writing anything.
