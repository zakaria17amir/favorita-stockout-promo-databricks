"""Plotly charts. Each function takes pandas and returns a go.Figure.

Colours and marks follow the dataviz reference palette: blue for a single series, blue + orange
for two (validated for colour-blind separation), a one-hue blue ramp for magnitude, hairline
grids, ≥ 8px markers with a surface ring, text in ink colours rather than series colours.
ponytail: light theme only; the standalone HTML has no dark variant. Add a dark template if the
charts get embedded in a themed page.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def _style(fig: go.Figure, title: str, subtitle: str, x_title: str, y_title: str = "", height: int = 480) -> go.Figure:
    axis = dict(gridcolor=GRID, gridwidth=1, linecolor=AXIS, zerolinecolor=AXIS, zerolinewidth=1,
                tickfont=dict(color=MUTED), title_font=dict(color=INK_2))
    fig.update_layout(
        title=dict(text=f"{title}<br><span style='font-size:13px;color:{INK_2}'>{subtitle}</span>",
                   font=dict(color=INK, size=18), x=0, xanchor="left"),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, height=height,
        font=dict(family=FONT, color=INK_2, size=13),
        margin=dict(l=16, r=fig.layout.margin.r or 24, b=fig.layout.margin.b or 48, t=fig.layout.margin.t or 88),
        hoverlabel=dict(bgcolor="white", bordercolor=GRID, font=dict(color=INK, family=FONT)),
        legend=dict(orientation="h", x=0, y=1.02, yanchor="bottom", font=dict(color=INK_2)),
    )
    fig.update_xaxes(title_text=x_title, **axis)
    fig.update_yaxes(title_text=y_title, automargin=True, **axis)
    return fig


def _pct(s: pd.Series) -> list[float]:
    return (s * 100).round(2).tolist()


def _signed(share: float) -> str:
    """0.42 → '+42%'; a value that rounds to zero prints as '0%', never '-0%'."""
    pct = round(share * 100)
    return f"{pct:+d}%" if pct else "0%"


def _dot(color: str) -> dict:
    return dict(size=9, color=color, line=dict(color=SURFACE, width=2))


def uplift_by_family(summary: pd.DataFrame) -> go.Figure:
    s = summary.sort_values("uplift_median")
    fig = go.Figure(go.Scatter(
        x=_pct(s.uplift_median), y=s.family, mode="markers", marker=_dot(BLUE),
        error_x=dict(type="data", symmetric=False, array=_pct(s.uplift_hi - s.uplift_median),
                     arrayminus=_pct(s.uplift_median - s.uplift_lo), color=BLUE, thickness=1.5, width=0),
        customdata=np.stack([s.n_events, _pct(s.uplift_lo), _pct(s.uplift_hi)], axis=-1),
        hovertemplate="<b>%{y}</b><br>Median uplift %{x:.1f}%<br>95% CI %{customdata[1]:.1f}% to "
                      "%{customdata[2]:.1f}%<br>%{customdata[0]:,} events<extra></extra>",
    ))
    fig.add_vline(x=0, line_color=AXIS, line_width=1)
    top = s.iloc[-1]
    return _style(fig, f"Promotions lift units most in {top.family} (+{top.uplift_median * 100:.0f}%)",
                  "Promo uplift by family: median extra units on promotion days vs. the item's normal baseline · 95% bootstrap CI",
                  "Uplift (%)", height=max(360, 22 * len(s) + 140))


def promo_payback(summary: pd.DataFrame) -> go.Figure:
    """Net lift per family: promotion + the following week against the baseline for both, so a promotion
    that only pulled sales forward nets out near zero. Colour says whether the 95% CI clears zero."""
    s = summary.dropna(subset=["net_median"]).sort_values("net_median")
    status = np.select([s.net_lo > 0, s.net_hi < 0], ["pays", "loses"], "unclear")
    fig = go.Figure()
    for key, name, color in (("pays", "Pays back (95% CI above 0)", BLUE),
                             ("unclear", "Unclear (CI spans 0)", MUTED),
                             ("loses", "Loses sales (CI below 0)", ORANGE)):
        g = s[status == key]
        if g.empty:
            continue
        fig.add_trace(go.Scatter(
            x=_pct(g.net_median), y=g.family, mode="markers", name=name, marker=_dot(color),
            error_x=dict(type="data", symmetric=False, array=_pct(g.net_hi - g.net_median),
                         arrayminus=_pct(g.net_median - g.net_lo), color=color, thickness=1.5, width=0),
            customdata=np.stack([_pct(g.uplift_median), _pct(g.dip_median), g.n_net_events], axis=-1),
            hovertemplate="<b>%{y}</b><br>Net lift %{x:.1f}%<br>During the promotion %{customdata[0]:+.0f}% · "
                          "week after %{customdata[1]:+.0f}%<br>%{customdata[2]:,} events with a clean week<extra></extra>",
        ))
    # the working behind each net number, as a muted text column right of the plot
    for _, r in s.iterrows():
        fig.add_annotation(xref="paper", x=1.01, xanchor="left", y=r.family, text=(
            f"{_signed(r.uplift_median)} lift · {_signed(r.dip_median)} after"),
            showarrow=False, font=dict(color=MUTED, size=11))
    fig.add_vline(x=0, line_color=AXIS, line_width=1)
    fig.update_yaxes(categoryorder="array", categoryarray=s.family.tolist())
    fig.update_layout(margin_t=120, margin_r=190)
    return _style(fig, f"Promotions still pay back in {(status == 'pays').sum()} of {len(s)} families",
                  "Net lift: units during the promotion and the week after vs. the item's normal baseline · "
                  "median per family, 95% bootstrap CI",
                  "Net lift after the post-promotion dip (%)", height=max(380, 22 * len(s) + 180))


def payday_check(events: pd.DataFrame, min_events: int = 30) -> go.Figure:
    g = events.groupby(["family", "touches_payday_or_holiday"])["uplift"].agg(["median", "size"]).reset_index()
    g = g[g["size"] >= min_events].pivot(index="family", columns="touches_payday_or_holiday", values="median").dropna()
    g = g.assign(gap=g[True] - g[False]).sort_values("gap")
    fig = go.Figure()
    for fam, r in g.iterrows():  # the connector between the two dots of a family
        fig.add_trace(go.Scatter(x=[r[False] * 100, r[True] * 100], y=[fam, fam], mode="lines",
                                 line=dict(color=GRID, width=2), hoverinfo="skip", showlegend=False))
    for col, name, color in ((False, "Other days", BLUE), (True, "Holiday or payday", ORANGE)):
        fig.add_trace(go.Scatter(x=_pct(g[col]), y=g.index, mode="markers", name=name, marker=_dot(color),
                                 hovertemplate=f"<b>%{{y}}</b><br>{name}: %{{x:.1f}}%<extra></extra>"))
    fig.update_layout(margin_t=120)  # room for the legend between subtitle and plot
    return _style(fig, f"Holidays and paydays inflate promo uplift in {(g.gap > 0).sum()} of {len(g)} families",
                  "Median uplift of promo events that touch a national holiday or payday (15th, month-end) vs. the rest",
                  "Median uplift (%)", height=max(360, 22 * len(g) + 160))


def stockout_heatmap(weekly: pd.DataFrame) -> go.Figure:
    """Stock-out rate (share of tested item-days inside a flagged run) per store and week, stores worst
    first, with each store's yearly rate as a bar alongside. Untested store-weeks stay blank."""
    w = weekly.assign(label="Store " + weekly.store_key.astype(str) + " · " + weekly.city.fillna("?"))
    per_store = w.groupby("label")[["flagged_days", "item_days"]].sum()
    per_store = (per_store.flagged_days / per_store.item_days).sort_values(ascending=False)
    order = per_store.index.tolist()
    grid = w.pivot_table(index="label", columns="week_start", values="rate", aggfunc="sum").reindex(order)
    z = (grid.to_numpy() * 100).round(4)
    weeks = [pd.Timestamp(c) for c in grid.columns]
    text = [[f"{lab}<br>Week of {wk:%d %b %Y}<br>" + ("not tested" if np.isnan(v) else f"{v:.1f}% of item-days empty")
             for wk, v in zip(weeks, row)] for lab, row in zip(order, z)]
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, column_widths=[0.82, 0.18], horizontal_spacing=0.015)
    fig.add_trace(go.Heatmap(
        z=z, x=weeks, y=order, text=text, hovertemplate="%{text}<extra></extra>", xgap=1, ygap=1,
        # capped at the 95th percentile so one extreme week doesn't wash out the rest
        zmin=0, zmax=float(np.nanpercentile(z, 95)),
        colorscale=[[i / (len(BLUE_RAMP) - 1), c] for i, c in enumerate(BLUE_RAMP)],
        colorbar=dict(title=dict(text="% of item-days empty", side="top"), orientation="h", x=0, xanchor="left",
                      y=-0.04, yanchor="top", len=0.4, thickness=10, outlinewidth=0),
    ), 1, 1)
    fig.add_trace(go.Bar(
        x=(per_store * 100).round(4).tolist(), y=order, orientation="h", showlegend=False,
        marker=dict(color=BLUE, cornerradius=4), hovertemplate="%{y}<br>%{x:.1f}% over the year<extra></extra>",
    ), 1, 2)
    fig.update_yaxes(autorange="reversed", tickmode="array", tickvals=order)  # every store labelled
    fig.update_xaxes(title_text="Whole year (%)", row=1, col=2)
    fig.update_layout(margin_b=90)
    return _style(fig, f"{order[0]} ran empty most often: {per_store.iloc[0]:.1%} of item-days",
                  "Share of tested item-days inside a flagged zero-sale run (5% FDR) per store and week · "
                  "worst stores first · colour capped at the 95th percentile",
                  "", height=max(460, 17 * len(order) + 200))


def poisson_check(disp: pd.DataFrame) -> go.Figure:
    d = disp["dispersion"][disp["dispersion"] > 0]
    share = (d > 1).mean()
    ticks = [0.25, 0.5, 1, 2, 4, 8, 16, 32]
    fig = go.Figure(go.Histogram(x=np.log10(d), nbinsx=60, marker=dict(color=BLUE, line=dict(color=SURFACE, width=1)),
                                 hovertemplate="%{y:,} store-items<extra></extra>"))
    fig.add_vline(x=0, line_color=INK_2, line_width=1, annotation_text="Poisson: variance = mean",
                  annotation_font=dict(color=INK_2, size=12), annotation_position="top right")
    fig.update_xaxes(tickvals=np.log10(ticks).tolist(), ticktext=[f"{t:g}" for t in ticks])
    fig.update_layout(bargap=0.05)
    return _style(fig, f"{share:.0%} of store-items vary more than Poisson assumes",
                  "Variance ÷ mean of daily units. Above 1, a Poisson test over-flags, so the run test uses a negative binomial",
                  "Variance ÷ mean (log scale)", "Store-items")


def save_all(figs: dict[str, go.Figure], out_dir) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, fig in figs.items():
        path = out / f"{name}.html"
        fig.write_html(path, include_plotlyjs="cdn", full_html=True)
        paths.append(path)
    return paths
