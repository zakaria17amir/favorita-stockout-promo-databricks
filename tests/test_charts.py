from datetime import date

import pandas as pd
import plotly.graph_objects as go

from favorita_spark import charts

SUMMARY = pd.DataFrame({
    "family": ["BEVERAGES", "DAIRY", "PRODUCE"],
    "n_events": [900, 400, 300],
    "uplift_median": [0.42, 0.18, 0.05],
    "uplift_lo": [0.38, 0.12, 0.01],
    "uplift_hi": [0.47, 0.24, 0.09],
    "n_dip_events": [800, 350, 20],
    "dip_median": [-0.08, -0.03, float("nan")],
    "dip_lo": [-0.10, -0.05, float("nan")],
    "dip_hi": [-0.06, -0.01, float("nan")],
})


def test_uplift_by_family_is_one_series_with_ci(tmp_path):
    fig = charts.uplift_by_family(SUMMARY)
    (trace,) = fig.data
    assert list(trace.y) == ["PRODUCE", "DAIRY", "BEVERAGES"]  # biggest uplift at the top
    assert list(trace.error_x.array) == [4.0, 6.0, 5.0]  # hi − median, in percentage points
    assert "Promo uplift by family" in fig.layout.title.text


def test_uplift_vs_dip_skips_families_without_a_dip():
    (trace,) = charts.uplift_vs_dip(SUMMARY).data
    assert list(trace.text) == ["BEVERAGES", "DAIRY"]


def test_payday_check_compares_two_groups():
    events = pd.DataFrame({
        "family": ["DAIRY"] * 8,
        "uplift": [0.1, 0.1, 0.2, 0.2, 0.5, 0.5, 0.7, 0.7],
        "touches_payday_or_holiday": [False] * 4 + [True] * 4,
    })
    fig = charts.payday_check(events, min_events=4)
    other, touching = fig.data[-2:]
    assert (other.name, touching.name) == ("Other days", "Holiday or payday")
    assert (list(other.x), list(touching.x)) == ([15.0], [60.0])


def test_stockout_heatmap_grid():
    weekly = pd.DataFrame({
        "store_key": [1, 1, 2],
        "week_start": [date(2016, 8, 15), date(2016, 8, 22), date(2016, 8, 15)],
        "flagged_runs": [3, 1, 5],
        "lost_units": [9.0, 2.0, 20.0],
    })
    (trace,) = charts.stockout_heatmap(weekly).data
    assert list(trace.y) == ["Store 1", "Store 2"]
    assert trace.z.tolist() == [[3, 1], [5, 0]]


def test_poisson_check_reports_overdispersion():
    fig = charts.poisson_check(pd.DataFrame({"dispersion": [0.5, 2.0, 4.0, 8.0]}))
    assert "75% of store-items" in fig.layout.title.text


def test_save_all_writes_html(tmp_path):
    paths = charts.save_all({"uplift": charts.uplift_by_family(SUMMARY)}, tmp_path)
    assert [p.name for p in paths] == ["uplift.html"]
    assert isinstance(charts.uplift_by_family(SUMMARY), go.Figure)
