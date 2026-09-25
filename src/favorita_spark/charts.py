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
        margin=dict(l=16, r=24, b=48, t=fig.layout.margin.t or 88),
        hoverlabel=dict(bgcolor="white", bordercolor=GRID, font=dict(color=INK, family=FONT)),
        legend=dict(orientation="h", x=0, y=1.02, yanchor="bottom", font=dict(color=INK_2)),
    )
    fig.update_xaxes(title_text=x_title, **axis)
    fig.update_yaxes(title_text=y_title, automargin=True, **axis)
    return fig


def _pct(s: pd.Series) -> list[float]:
    return (s * 100).round(2).tolist()


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
    return _style(fig, "Promo uplift by family",
                  "Median extra units on promotion days vs. the item's normal baseline · 95% bootstrap CI",
                  "Uplift (%)", height=max(360, 22 * len(s) + 140))


def uplift_vs_dip(summary: pd.DataFrame) -> go.Figure:
    s = summary.dropna(subset=["dip_median"])
    fig = go.Figure(go.Scatter(
        x=_pct(s.uplift_median), y=_pct(s.dip_median), text=s.family.tolist(), mode="markers", marker=_dot(BLUE),
        hovertemplate="<b>%{text}</b><br>Uplift %{x:.1f}%<br>Post-promo dip %{y:.1f}%<extra></extra>",
    ))
    # label only the two extremes (biggest lift, deepest dip); the tooltip carries the rest
    for _, r in pd.concat([s.nlargest(1, "uplift_median"), s.nsmallest(1, "dip_median")]).drop_duplicates("family").iterrows():
        fig.add_annotation(x=r.uplift_median * 100, y=r.dip_median * 100, text=r.family, showarrow=False,
                           xanchor="left", xshift=8, font=dict(color=INK_2, size=12))
    fig.add_hline(y=0, line_color=AXIS, line_width=1)
    return _style(fig, "Does a bigger lift mean a bigger hangover?",
                  "Median promo uplift vs. median change in the 7 days after, per family",
                  "Uplift during promotion (%)", "Change in the week after (%)")


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
    return _style(fig, "Holidays and paydays flatter promotions",
                  "Median uplift of promo events that touch a national holiday or payday (15th, month-end) vs. the rest",
                  "Median uplift (%)", height=max(360, 22 * len(g) + 160))


def stockout_heatmap(weekly: pd.DataFrame, value: str = "flagged_runs") -> go.Figure:
    grid = weekly.pivot_table(index="store_key", columns="week_start", values=value, aggfunc="sum", fill_value=0)
    fig = go.Figure(go.Heatmap(
        z=grid.to_numpy(), x=[pd.Timestamp(w) for w in grid.columns], y=[f"Store {s}" for s in grid.index],
        colorscale=[[i / (len(BLUE_RAMP) - 1), c] for i, c in enumerate(BLUE_RAMP)], xgap=2, ygap=2,
        colorbar=dict(title=dict(text="Flagged runs" if value == "flagged_runs" else "Lost units"), outlinewidth=0),
        hovertemplate="%{y}, week of %{x|%d %b %Y}<br>%{z:,}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed")
    return _style(fig, "Where and when shelves ran empty",
                  "Zero-sale runs flagged at a 5% false discovery rate, per store and week",
                  "", height=max(420, 14 * len(grid) + 160))


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
                  "Variance ÷ mean of daily units. Above 1, the run test over-flags; a negative-binomial model would fix it",
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
