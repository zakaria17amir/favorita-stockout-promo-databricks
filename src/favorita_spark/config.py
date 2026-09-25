from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Config:
    catalog: str = "workspace"
    raw_path: str = "/Volumes/workspace/bronze/raw"
    raw_ext: str = ".csv.gz"
    # raw slice = analysis window + 56-day burn-in, so trailing windows are complete on day one
    slice_start: date = date(2016, 6, 21)
    window_start: date = date(2016, 8, 16)
    window_end: date = date(2017, 8, 15)
    lookback_days: int = 28
    min_expected_units: float = 3.0
    min_receipts_share: float = 0.5  # of the store's trailing average
    post_promo_days: int = 7
    max_run_days: int = 28  # longer zero-sale gaps look like delisting, not a stock-out
    fdr_q: float = 0.05
    bootstrap_resamples: int = 1000
    min_family_events: int = 30
    seed: int = 42

    def sql_params(self) -> dict[str, str]:
        return {
            "stockout_from": self.window_start.isoformat(),
            "lookback_days": str(self.lookback_days),
            "min_expected_units": str(self.min_expected_units),
            "min_receipts_share": str(self.min_receipts_share),
            "post_promo_days": str(self.post_promo_days),
        }
