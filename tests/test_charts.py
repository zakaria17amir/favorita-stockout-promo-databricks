from datetime import date

import pandas as pd
import plotly.graph_objects as go

from favorita_spark import charts

SUMMARY = pd.DataFrame({
    "family": ["BEVERAGES", "DAIRY", "PRODUCE", "BREAD"],
    "n_events": [900, 400, 300, 200],
    "uplift_median": [0.42, 0.18, 0.05, 0.30],
    "uplift_lo": [0.38, 0.12, 0.01, 0.25],
    "uplift_hi": [0.47, 0.24, 0.09, 0.35],
    "n_dip_events": [800, 350, 20, 150],
    "dip_median": [-0.08, -0.03, float("nan"), -0.40],
    "dip_lo": [-0.10, -0.05, float("nan"), -0.45],
    "dip_hi": [-0.06, -0.01, float("nan"), -0.35],
    "n_net_events": [800, 350, 20, 150],
    "net_median": [0.12, 0.02, float("nan"), -0.10],
    "net_lo": [0.09, -0.01, float("nan"), -0.15],
    "net_hi": [0.15, 0.05, float("nan"), -0.05],
})


def test_uplift_by_family_is_one_series_with_ci():
    fig = charts.uplift_by_family(SUMMARY)
    (trace,) = fig.data
    assert list(trace.y) == ["PRODUCE", "DAIRY", "BREAD", "BEVERAGES"]  # biggest uplift at the top
    assert list(trace.error_x.array) == [4.0, 6.0, 5.0, 5.0]  # hi − median, in percentage points
    assert "BEVERAGES (+42%)" in fig.layout.title.text  # the title states the finding


def test_promo_payback_groups_families_by_their_ci():
    fig = charts.promo_payback(SUMMARY)
    groups = {t.name: list(t.y) for t in fig.data}
    assert groups == {"Pays back (95% CI above 0)": ["BEVERAGES"],
                      "Unclear (CI spans 0)": ["DAIRY"],
                      "Loses sales (CI below 0)": ["BREAD"]}  # PRODUCE has no clean week → left out
    assert list(fig.layout.yaxis.categoryarray) == ["BREAD", "DAIRY", "BEVERAGES"]  # sorted by net lift
    assert "1 of 3 families" in fig.layout.title.text
    assert any("+42% lift · -8% after" in a.text for a in fig.layout.annotations)


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
    assert "1 of 1 families" in fig.layout.title.text


WEEKLY = pd.DataFrame({
    "store_key": [1, 1, 2, 2, 3],
    "city": ["Quito", "Quito", "Cuenca", "Cuenca", "Loja"],
    "week_start": [date(2016, 8, 15), date(2016, 8, 22), date(2016, 8, 15), date(2016, 8, 22), date(2016, 8, 22)],
    "flagged_days": [10, 30, 2, 0, 5],
    "item_days": [1000, 1000, 100, 100, 50],
    "rate": [0.01, 0.03, 0.02, 0.0, 0.1],
})


def test_stockout_heatmap_ranks_stores_by_rate():
    fig = charts.stockout_heatmap(WEEKLY)
    heat, bars = fig.data
    # yearly rates: store 3 = 10%, store 1 = 2%, store 2 = 1% → worst first
    assert list(heat.y) == ["Store 3 · Loja", "Store 1 · Quito", "Store 2 · Cuenca"]
    assert [round(v, 6) for v in bars.x] == [10.0, 2.0, 1.0]
    z = heat.z
    assert pd.isna(z[0][0])  # store 3 wasn't tested in the first week: blank, not zero
    assert (z[1][0], z[1][1], z[2][1]) == (1.0, 3.0, 0.0)
    assert "Store 3 · Loja" in fig.layout.title.text


def test_poisson_check_reports_overdispersion():
    fig = charts.poisson_check(pd.DataFrame({"dispersion": [0.5, 2.0, 4.0, 8.0]}))
    assert "75% of store-items" in fig.layout.title.text


def test_save_all_writes_html(tmp_path):
    paths = charts.save_all({"uplift": charts.uplift_by_family(SUMMARY)}, tmp_path)
    assert [p.name for p in paths] == ["uplift.html"]
    assert isinstance(charts.uplift_by_family(SUMMARY), go.Figure)
