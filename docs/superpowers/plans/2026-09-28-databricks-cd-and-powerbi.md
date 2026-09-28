# Databricks CD + Power BI deep-dive: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Deploy the pipeline as a Databricks Job from GitHub, and add a Databricks-fed deep-dive report to Project 1.
**Spec:** `docs/superpowers/specs/2026-09-28-databricks-cd-and-powerbi-design.md`

## Global constraints
- No Claude attribution in commits or PRs.
- Never run the Databricks job automatically; deploy only. Runs happen from `workflow_dispatch` or by hand.
- CLI and action version 1.18.0. The workspace host is `https://dbc-ecb852ca-9ebf.cloud.databricks.com`.
- Project 1 changes go on a branch with a PR; CI (pytest + BPA) must pass there.

## Part 1: this repo
- [ ] **T1** `weekly_stockout_rate` adds `week_start_key`. A test asserts `20160104`. Notebook 04 writes `gold.stockout_store_week`
  and adds `poisson_flagged_runs` to `gold.stockout_bh_summary`. Notebook 06 reads the table. 07 exports it.
- [ ] **T2** `databricks.yml` (job with 8 tasks, `dev` and `prod` targets). `databricks bundle validate -t prod` passes locally.
- [ ] **T3** `ci.yml`: `tests` → `bundle-validate` → `deploy` (push to main) / `run` (manual). The Databricks steps
  are skipped without the secret. Add a README "Deploy" section. Commit and push; CI is green with the secret unset.

## Part 2: Project 1 (`../Flagship`, branch `feat/databricks-deep-dive`)
- [ ] **T4** Model: parameters, 5 tables, 5 relationships, measures, role permissions, `model.tmdl` refs and query order.
- [ ] **T5** `test_model_contract.py`: the Databricks reads are documented (tables and columns). The existing pytest suite passes.
- [ ] **T6** `DeepDive.Report` + `DeepDive.pbip`, copying Promotions.Report's page and visual patterns and theme.
- [ ] **T7** Docs: ADR-012, architecture, KPI glossary, security, fabric/README. This repo's ADR-002 gets its correction.
- [ ] **T8** Push the branch and open the PR (no attribution). Report the CI result.
