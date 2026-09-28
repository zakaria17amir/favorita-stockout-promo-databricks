# Databricks CD + Power BI deep-dive: design

- Date: 2026-09-28
- Status: approved in chat (2026-09-28)
- Decisions: Power BI reads Databricks **live in every stage** (option A); "CI/CD" means **Databricks CD**
  through an Asset Bundle and GitHub Actions. Power BI promotion stays manual in the Fabric deployment pipeline.

## Part 1: this repo

### Bundle (`databricks.yml`)
- One job, `favorita_pipeline` (`favorita-pipeline`): notebooks 00 → 07 as eight sequential serverless tasks
  (`setup`, `bronze`, `silver`, `gold_contract`, `stockout_runs`, `promo_events`, `charts`, `export`), with
  `max_concurrent_runs: 1`.
- Targets:
  - `dev`: `mode: development`, the default, for deploys from a laptop.
  - `prod`: `mode: production`, with an explicit `root_path`, deployed by GitHub Actions.
- The workspace host lives in the file, because it isn't secret. The only secret is `DATABRICKS_TOKEN`.

### GitHub Actions (`.github/workflows/ci.yml`)
| Trigger | Jobs |
|---|---|
| pull request | `tests` (pytest, Java 17), then `bundle-validate` (`databricks bundle validate -t prod`) |
| push to `main` | `tests`, then `bundle-validate`, then `deploy` (`databricks bundle deploy -t prod`), without running the job |
| manual (`workflow_dispatch`, input `run_pipeline`) | the same as above, plus `databricks bundle run favorita_pipeline -t prod` |

The job never runs automatically, because each run uses part of the Free Edition daily compute cap. The
Databricks steps are skipped, with a notice, while the `DATABRICKS_TOKEN` secret isn't set, so CI stays green
before the secret exists.

### Pipeline additions
- `gold.stockout_store_week`: `weekly_stockout_rate(...)` with a new `week_start_key` column
  (`yyyyMMdd` integer, for the Power BI Date relationship). Notebook 04 writes it, notebook 06 reads it, and
  notebook 07 exports it.
- `gold.stockout_bh_summary` gains `poisson_flagged_runs`: Benjamini–Hochberg applied to `p_poisson` on the same runs.

## Part 2: Project 1 (`store-performance-fabric`), branch `feat/databricks-deep-dive`, pull request

### Model
- Parameters: `DatabricksHost` and `DatabricksHttpPath`, the same in every stage (no deployment rule).
- Source: `Databricks.Catalogs(DatabricksHost, DatabricksHttpPath, [Catalog = null, Database = null,
  EnableAutomaticProxyDiscovery = null])` → `workspace` → `gold`, in Import mode.
- New tables:

| Table | Source | Filter / grain | Relationships |
|---|---|---|---|
| Stock-out Run | `fact_stockout_run` | `is_flagged` only (~273k) | StartDateKey → Date, StoreKey → Store, ItemKey → Item |
| Stock-out Store Week | `stockout_store_week` | store × week (~2.8k) | WeekStartKey → Date, StoreKey → Store |
| Promo Event | `fact_promo_event` | event (~1.6M) | StartDateKey → Date, StoreKey → Store, ItemKey → Item |
| Promo Payback | `promo_family_summary` | family (29) | none (network level) |
| Stock-out Test | `stockout_bh_summary` | 1 row | none |

- Security: the facts inherit the Store row filter. `Store operations` gets `tablePermission = FALSE()` on
  Promo Payback and Stock-out Test, because they are network-wide numbers.
- Measures (display folder `Databricks deep dive`, each with a description): Flagged Runs, Stock-out Rate %,
  Lost Units (Runs), Median Uplift %, Median Net Lift %, Families Paying Back, NB Flag Rate %, Poisson Flag Rate %.

### Report
- `DeepDive.Report` / `DeepDive.pbip`, one page, "Stock-outs & promo payback", in the Project 1 theme.
- Visuals: a KPI card row, stock-out rate by store (bar), a store × month rate matrix (conditional formatting),
  net lift by family (bar, with the CI in the tooltip), and region and date slicers.
- App audiences: regional managers, category managers, head office.

### CI and docs
- `test_model_contract.py`: Databricks partitions may read only the documented tables and columns.
- BPA: new columns use int64/decimal, hidden keys have `isAvailableInMdx: false`, and measures have descriptions
  and format strings.
- Docs: ADR-012 (Databricks as a second model source, including the refresh-dependency risk), plus architecture,
  KPI glossary, security, fabric/README. This repo's ADR-002 is corrected: an Import refresh *does* depend on the source.

## Manual steps (owner)
1. Create a long-lived personal access token and add `DATABRICKS_TOKEN` as a GitHub secret on this repo.
2. In Fabric, create an Azure Databricks cloud connection (personal access token) and map it in the semantic
   model settings in each workspace.
3. Merge the Project 1 PR; Fabric syncs it to Dev. Refresh and check the report, then promote Test → Prod.
4. Add DeepDive to the app audiences.
