"""
Plotly chart builders. Each function takes a prepared table and returns a figure.
No data calculation happens here: charts only DRAW what analytics.py computed.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config

TEMPLATE = "plotly_white"
PRIMARY = "#1f77b4"
ACCENT = "#ff7f0e"
CURRENCY = config.CURRENCY_SYMBOL
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _style(fig: go.Figure, title: str, height: int = 380) -> go.Figure:
    fig.update_layout(title=title, template=TEMPLATE, height=height,
                      margin=dict(l=10, r=10, t=60, b=10), legend_title_text="")
    return fig


def revenue_trend_chart(monthly: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=monthly["month"], y=monthly["revenue"], mode="lines+markers",
                             name="Monthly revenue", line=dict(color=PRIMARY)))
    fig.add_trace(go.Scatter(x=monthly["month"], y=monthly["revenue_ma3"], mode="lines",
                             name="3-month average", line=dict(color=ACCENT, dash="dash")))
    fig.update_yaxes(title_text=f"Revenue ({CURRENCY})")
    return _style(fig, "Monthly revenue trend")


def bar_chart(table: pd.DataFrame, category_col: str, value_col: str, title: str,
              horizontal: bool = True, color: str = PRIMARY) -> go.Figure:
    if horizontal:
        fig = px.bar(table, x=value_col, y=category_col, orientation="h")
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
    else:
        fig = px.bar(table, x=category_col, y=value_col)
    fig.update_traces(marker_color=color)
    return _style(fig, title)


def donut_chart(table: pd.DataFrame, names_col: str, values_col: str, title: str) -> go.Figure:
    fig = px.pie(table, names=names_col, values=values_col, hole=0.5)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return _style(fig, title)


def pareto_chart(pareto: pd.DataFrame, dim: str, top_n: int = 25) -> go.Figure:
    data = pareto.head(top_n)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=data[dim], y=data["revenue"], name="Revenue",
                         marker_color=PRIMARY), secondary_y=False)
    fig.add_trace(go.Scatter(x=data[dim], y=data["cumulative_share_pct"], mode="lines+markers",
                             name="Cumulative %", line=dict(color=ACCENT)), secondary_y=True)
    fig.add_trace(go.Scatter(x=data[dim], y=[config.PARETO_THRESHOLD_PCT] * len(data),
                             mode="lines", name=f"{config.PARETO_THRESHOLD_PCT}% line",
                             line=dict(color="grey", dash="dot")), secondary_y=True)
    fig.update_yaxes(title_text=f"Revenue ({CURRENCY})", secondary_y=False)
    fig.update_yaxes(title_text="Cumulative share (%)", range=[0, 105], secondary_y=True)
    return _style(fig, f"Pareto analysis by {dim}")


def growth_chart(monthly: pd.DataFrame, metric: str = "mom_growth_pct") -> go.Figure:
    label = "Month-over-month growth (%)" if metric == "mom_growth_pct" \
        else "Year-over-year growth (%)"
    data = monthly.dropna(subset=[metric])
    colors = [PRIMARY if v >= 0 else "#d62728" for v in data[metric]]
    fig = go.Figure(go.Bar(x=data["month"], y=data[metric], marker_color=colors))
    fig.update_yaxes(title_text="%")
    return _style(fig, label)


def seasonality_heatmap(monthly: pd.DataFrame) -> go.Figure:
    data = monthly.copy()
    data["year"] = data["month"].dt.year
    data["month_num"] = data["month"].dt.month
    pivot = data.pivot_table(index="year", columns="month_num", values="revenue", aggfunc="sum")
    pivot = pivot.reindex(columns=range(1, 13))
    fig = go.Figure(go.Heatmap(
        z=pivot.to_numpy(), x=MONTH_NAMES, y=[str(y) for y in pivot.index],
        colorscale="Blues", colorbar=dict(title=CURRENCY)))
    return _style(fig, "Revenue by month and year (seasonality)", height=300)


def forecast_chart(history: pd.DataFrame, forecast: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history["month"], y=history["revenue"], mode="lines+markers",
                             name="Actual", line=dict(color=PRIMARY)))
    fig.add_trace(go.Scatter(x=forecast["month"], y=forecast["upper"], mode="lines",
                             line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=forecast["month"], y=forecast["lower"], mode="lines",
                             line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(255,127,14,0.2)", name="Approx. range"))
    fig.add_trace(go.Scatter(x=forecast["month"], y=forecast["forecast"], mode="lines+markers",
                             name="Forecast", line=dict(color=ACCENT, dash="dash")))
    fig.update_yaxes(title_text=f"Revenue ({CURRENCY})")
    return _style(fig, "Revenue forecast")
