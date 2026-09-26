# ADR-003: Negative-binomial run test instead of Poisson

- Status: Accepted (2026-09-26)

## Context
The first design tested zero-sale runs against a Poisson baseline, p = e^(−λk), with Benjamini–Hochberg at a
5% false discovery rate. A local run on real data (3 stores, 231,323 tested runs) showed that demand varies far
more than Poisson allows. The median variance ÷ mean per store-item was 4.4, and 99.9% of store-items were
above 1. Zero days are therefore much commoner than Poisson predicts, and the test flagged 38% of all runs
(88,212). That's not a credible stock-out rate.

## Decision
Use a negative binomial with the same mean λ and the item's dispersion φ = variance ÷ mean. Both come from
the previous 28 trading days, so nothing is computed from after the run starts. A zero day has probability
φ^(−λ/(φ−1)), and a run of k full days has p = φ^(−λk/(φ−1)). When φ ≤ 1 the formula is replaced by Poisson,
which it converges to. The Poisson p-value stays in the table as `p_poisson`.

## Consequences
+ On the same trial the test flags 11.4% of runs (26,388; BH cut-off 5.7e-3, so at most 1,319 are chance), against
  38.1% for Poisson. It's still one formula to explain in an interview: "Poisson plus the item's own variability."
+ The trailing 28-day φ (median 2.0 at run start) avoids look-ahead. A prototype that used each item's variance over
  the whole year flagged 7.5%, but that year includes days after the run, so it was rejected.
+ Each flag's `p_poisson` next to its `p_value` shows how much the correction mattered.
− A 28-day variance is a noisy estimate. An earlier stock-out inside those 28 days inflates it, which makes
  the test more conservative (fewer flags), not less.
− Days are still treated as independent. Real stock-outs persist, so p is a ranking score for flagging, not an
  exact probability.
