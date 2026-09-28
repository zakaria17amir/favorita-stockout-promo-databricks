# ADR-002: How Power BI reads the Databricks gold tables

- Status: Accepted (2026-09-26, after the day-one connector test)

## Context
Project 1 (Store Performance Cockpit) should read these gold tables in two ways:
- the contract tables, with the same grain and columns as its own gold tables;
- the new analysis tables (`fact_stockout_run`, `fact_promo_event`, `promo_family_summary`).

The Free Edition documentation doesn't say whether BI tools can authenticate with a personal access token.

## Options
1. **Power BI Azure Databricks connector, personal access token, the SQL warehouse (Import mode).** This is live,
   but it depends on token login working on Free Edition and on the 2X-Small warehouse being awake at refresh time.
2. **Parquet export → OneLake.** Notebook 07 writes Parquet to a volume; it's downloaded and uploaded to the Project 1
   lakehouse (Files → Load to Tables). This always works, but it's a manual copy.

## Decision
**Option 1.** The day-one test succeeded. Option 2 stays as the documented fallback. Import mode in both cases,
because the analysis tables are small.

*Correction (2026-09-28):* an earlier version said Import "keeps Project 1's refresh independent of a free
warehouse". That's wrong. An Import refresh reads every source, so if Databricks is unavailable, Project 1's whole
model fails to refresh. Project 1 accepts that risk for a manually refreshed demo; see its
[ADR-012](https://github.com/zakaria17amir/store-performance-fabric/blob/main/docs/decisions/ADR-012-databricks-second-source.md).

## Test result
- **2026-09-26: works.** Power BI Desktop loaded `workspace.gold.connector_check` (one row: "hello from
  Databricks Free Edition" plus a timestamp) from the Free Edition SQL warehouse with a personal access token, in Import mode.
- **Gotcha:** the first attempt, with the plain **Databricks** connector, failed with
  `ADBC: Required parameter 'adbc.spark.host' or 'uri' is missing or invalid`. Microsoft's docs reserve that
  connector for AWS warehouses that use OAuth. With a personal access token, use the **Azure Databricks** connector
  (it works for AWS workspaces too), and enter the server hostname without `https://` or a trailing slash.

## Consequences
+ Either way, Project 1's existing model is unchanged. The new tables go on a separate deep-dive page.
− Option 2 needs a manual copy per refresh, which is acceptable for a 12-month analysis that doesn't change daily.
