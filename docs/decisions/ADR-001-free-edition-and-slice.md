# ADR-001: Databricks Free Edition with a 12-month slice

- Status: Accepted (2026-09-26)

## Context
Free Edition only offers serverless compute and one 2X-Small SQL warehouse. It has a daily usage cap: once
the cap is exceeded, compute shuts down for the rest of the day. Outbound internet is restricted, so
the Kaggle files can't be downloaded from a notebook. The full Favorita history is about 125M rows.

## Decision
Analyse the last 12 months (2016-08-16 → 2017-08-15) plus a 56-day burn-in, so every 28-day trailing window
and the stock-out spine are complete on day one. `scripts/slice_raw.py` (DuckDB) date-filters `train.csv`
locally and keeps the rows as raw text. The small files are kept whole, including `transactions` so store opening
dates use full history. The output is 42.8M sales rows, 297 MB gzipped, uploaded to a Unity Catalog volume.

## Consequences
+ One full run fits comfortably inside the daily cap, and the upload stays under the 5 GB UI limit.
+ The raw data is untouched apart from the date filter, so bronze still means "raw".
− Items whose previous sale falls before the burn-in get a later first sale than in Project 1. This can null a
  few baselines near the window start. The reconciliation allows this (≤ 0.1%) and reports it.
− Year-over-year comparisons aren't possible inside this project. Project 1 keeps the full history.
