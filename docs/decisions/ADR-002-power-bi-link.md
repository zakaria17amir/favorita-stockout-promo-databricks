# ADR-002: How Power BI reads the Databricks gold tables

- Status: Proposed. It becomes Accepted after the day-one connector test.

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
Option 1 if the day-one test (notebook `00_setup`) succeeds, otherwise option 2. Import mode in both cases:
the analysis tables are small, and Import keeps Project 1's refresh independent of a free warehouse.

## Test result
_Fill in: date, Power BI Desktop version, works / fails, error message if any._

## Consequences
+ Either way, Project 1's existing model is unchanged. The new tables go on a separate deep-dive page.
− Option 2 needs a manual copy per refresh, which is acceptable for a 12-month analysis that doesn't change daily.
