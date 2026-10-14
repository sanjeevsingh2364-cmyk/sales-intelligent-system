"""
Analytics engine: pure functions that take the CLEAN DataFrame and return numbers
or small tables. No Streamlit and no plotting here, so everything is easy to test.

Calculation grain (important for interviews):
  * One row of the data = one product line of an order.
  * Revenue / units are summed over ROWS.
  * Orders and customers are counted as DISTINCT order_id / customer_id.
  * Average Order Value (AOV) = total revenue / DISTINCT orders (not / rows).
  * Revenue = quantity * unit_price * (1 - discount).
  * Profit  = revenue - quantity * unit_cost (product cost only, no overheads).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config


# =============================================================================
# Small helpers
# =============================================================================
def format_currency(value: float) -> str:
    return f"{config.CURRENCY_SYMBOL}{value:,.0f}"


def _has_profit(df: pd.DataFrame) -> bool:
    return "profit" in df.columns and bool(df["profit"].notna().any())


def _safe_pct_change(series: pd.Series, periods: int) -> pd.Series:
    """Percent change vs `periods` rows earlier; NaN when the base is zero/missing."""
    previous = series.shift(periods)
    change = (series - previous) / previous * 100
    return change.where(previous > 0)


# =============================================================================
# Filtering
# =============================================================================
def apply_filters(
    df: pd.DataFrame,
    start_date=None,
    end_date=None,
    regions=None,
    categories=None,
    products=None,
) -> pd.DataFrame:
    """Filter rows. `None` = no filter on that field; an EMPTY list = no rows."""
    mask = pd.Series(True, index=df.index)
    if start_date is not None:
        mask &= df["order_date"] >= pd.Timestamp(start_date)
    if end_date is not None:  # inclusive of the whole end day
        mask &= df["order_date"] < pd.Timestamp(end_date) + pd.Timedelta(days=1)
    if regions is not None:
        mask &= df["region"].isin(regions)
    if categories is not None:
        mask &= df["category"].isin(categories)
    if products is not None:
        mask &= df["product"].isin(products)
    return df.loc[mask].copy()


# =============================================================================
# KPIs
# =============================================================================
def calculate_kpis(df: pd.DataFrame) -> dict:
    """Headline KPIs. Profit fields are None when cost data is not available."""
    kpis = {
        "total_revenue": 0.0,
        "total_orders": 0,
        "total_units": 0.0,
        "average_order_value": 0.0,
        "unique_customers": 0,
        "discount_rate_pct": 0.0,
        "gross_profit": None,
        "profit_margin_pct": None,
    }
    if df.empty:
        return kpis

    revenue = float(df["revenue"].sum())
    orders = int(df["order_id"].nunique())
    gross = float(df["gross_sales"].sum())

    kpis.update(
        total_revenue=revenue,
        total_orders=orders,
        total_units=float(df["quantity"].sum()),
        average_order_value=revenue / orders if orders else 0.0,
        unique_customers=int(df["customer_id"].nunique()),
        discount_rate_pct=(gross - revenue) / gross * 100 if gross else 0.0,
    )
    if _has_profit(df):
        costed = df.loc[df["profit"].notna()]
        base = float(costed["revenue"].sum())  # margin only over rows with known cost
        kpis["gross_profit"] = float(costed["profit"].sum())
        kpis["profit_margin_pct"] = kpis["gross_profit"] / base * 100 if base else None
    return kpis


# =============================================================================
# Breakdowns: product / category / region / customer
# =============================================================================
def sales_by_dimension(df: pd.DataFrame, dim: str, top_n: int | None = None) -> pd.DataFrame:
    """Revenue, units, orders, share (and profit/margin) per value of `dim`."""
    base_cols = [dim, "revenue", "units", "orders", "revenue_share_pct"]
    if df.empty:
        return pd.DataFrame(columns=base_cols)

    aggregations = {
        "revenue": ("revenue", "sum"),
        "units": ("quantity", "sum"),
        "orders": ("order_id", "nunique"),
    }
    if dim == "product" and "category" in df.columns:
        aggregations["category"] = ("category", "first")
    has_profit = _has_profit(df)
    if has_profit:
        aggregations["profit"] = ("profit", "sum")
        aggregations["revenue_costed"] = ("revenue_costed", "sum")

    out = (
        df.groupby(dim, as_index=False)
        .agg(**aggregations)
        .sort_values("revenue", ascending=False)
        .reset_index(drop=True)
    )
    total = out["revenue"].sum()
    out["revenue_share_pct"] = out["revenue"] / total * 100 if total else 0.0
    if has_profit:
        out["margin_pct"] = np.where(
            out["revenue_costed"] > 0, out["profit"] / out["revenue_costed"] * 100, np.nan
        )
        out = out.drop(columns="revenue_costed")
    return out.head(top_n) if top_n else out


def top_and_bottom(df: pd.DataFrame, dim: str = "product", n: int = 5):
    """(top n, bottom n) by revenue."""
    table = sales_by_dimension(df, dim)
    return table.head(n), table.tail(n).sort_values("revenue").reset_index(drop=True)


def pareto_analysis(df: pd.DataFrame, dim: str = "product") -> pd.DataFrame:
    """Cumulative revenue share. 'Core contributors' = items needed to reach 80%."""
    table = sales_by_dimension(df, dim)
    if table.empty:
        return pd.DataFrame(
            columns=["rank", dim, "revenue", "revenue_share_pct",
                     "cumulative_share_pct", "is_core_contributor"]
        )
    table = table[[dim, "revenue", "revenue_share_pct"]].copy()
    table["cumulative_share_pct"] = table["revenue_share_pct"].cumsum().clip(upper=100)
    share_before = table["cumulative_share_pct"] - table["revenue_share_pct"]
    table["is_core_contributor"] = share_before < config.PARETO_THRESHOLD_PCT
    table.insert(0, "rank", np.arange(1, len(table) + 1))
    return table


def pareto_summary(pareto: pd.DataFrame) -> dict:
    total = len(pareto)
    core = int(pareto["is_core_contributor"].sum()) if total else 0
    return {
        "core_items": core,
        "total_items": total,
        "core_items_pct": core / total * 100 if total else 0.0,
    }


def period_growth_by_dimension(
    df: pd.DataFrame, dim: str, window_days: int = config.GROWTH_WINDOW_DAYS
) -> pd.DataFrame:
    """Recent window vs the window before it (default: last 12 months vs previous 12).

    Returns an EMPTY table unless the data covers both windows, to avoid
    comparing a full period with a partial one.
    """
    cols = [dim, "recent_revenue", "prior_revenue", "growth_pct"]
    if df.empty:
        return pd.DataFrame(columns=cols)

    end = df["order_date"].max()
    recent_start = end - pd.Timedelta(days=window_days)
    prior_start = end - pd.Timedelta(days=2 * window_days)
    if df["order_date"].min() > prior_start + pd.Timedelta(days=7):
        return pd.DataFrame(columns=cols)

    recent = df.loc[df["order_date"] > recent_start].groupby(dim)["revenue"].sum()
    prior = df.loc[
        (df["order_date"] > prior_start) & (df["order_date"] <= recent_start)
    ].groupby(dim)["revenue"].sum()

    out = (
        pd.concat([recent.rename("recent_revenue"), prior.rename("prior_revenue")], axis=1)
        .fillna(0.0)
        .rename_axis(dim)
        .reset_index()
    )
    out["growth_pct"] = np.where(
        out["prior_revenue"] > 0,
        (out["recent_revenue"] - out["prior_revenue"]) / out["prior_revenue"] * 100,
        np.nan,
    )
    return out.sort_values("growth_pct", ascending=False).reset_index(drop=True)


# =============================================================================
# Time series: monthly / quarterly / yearly
# =============================================================================
def monthly_sales(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly revenue, orders, units + 3-month average, MoM % and YoY %.

    Months with no sales are filled with 0 so that shift(1) really means
    'previous month' and shift(12) really means 'same month last year'.
    """
    cols = ["month", "revenue", "orders", "units", "revenue_ma3",
            "mom_growth_pct", "yoy_growth_pct"]
    if df.empty:
        return pd.DataFrame(columns=cols)

    grouped = df.groupby("month").agg(
        revenue=("revenue", "sum"),
        orders=("order_id", "nunique"),
        units=("quantity", "sum"),
    )
    full_index = pd.date_range(grouped.index.min(), grouped.index.max(), freq="MS")
    grouped = grouped.reindex(full_index, fill_value=0)
    grouped.index.name = "month"
    grouped["revenue_ma3"] = grouped["revenue"].rolling(3, min_periods=1).mean()
    grouped["mom_growth_pct"] = _safe_pct_change(grouped["revenue"], 1)
    grouped["yoy_growth_pct"] = _safe_pct_change(grouped["revenue"], 12)
    return grouped.reset_index()[cols]


def drop_incomplete_last_month(monthly: pd.DataFrame, last_order_date) -> pd.DataFrame:
    """Remove the last month if data stops before the month ends (partial month)."""
    if monthly.empty:
        return monthly
    last_order_date = pd.Timestamp(last_order_date)
    last_month = monthly["month"].iloc[-1]
    month_end = last_month + pd.offsets.MonthEnd(0)
    if last_order_date.normalize() < month_end.normalize():
        return monthly.iloc[:-1].reset_index(drop=True)
    return monthly


def sales_by_period(df: pd.DataFrame, period: str = "quarter") -> pd.DataFrame:
    """Revenue per 'quarter' or 'year', with growth vs the previous period shown."""
    if period not in ("quarter", "year"):
        raise ValueError("period must be 'quarter' or 'year'")
    if df.empty:
        return pd.DataFrame(columns=[period, "revenue", "orders", "units", "growth_pct"])
    out = (
        df.groupby(period)
        .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"),
             units=("quantity", "sum"))
        .sort_index()
        .reset_index()
    )
    out["growth_pct"] = _safe_pct_change(out["revenue"], 1)
    return out


# =============================================================================
# Customers
# =============================================================================
def customer_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["customer_id", "orders", "units", "revenue",
                                     "first_order", "last_order", "avg_order_value"])
    out = df.groupby("customer_id").agg(
        orders=("order_id", "nunique"),
        units=("quantity", "sum"),
        revenue=("revenue", "sum"),
        first_order=("order_date", "min"),
        last_order=("order_date", "max"),
    ).reset_index()
    out["avg_order_value"] = out["revenue"] / out["orders"]
    return out.sort_values("revenue", ascending=False).reset_index(drop=True)


def repeat_purchase_metrics(df: pd.DataFrame) -> dict:
    """Repeat customer = 2+ distinct orders INSIDE the selected filters."""
    customers = customer_summary(df)
    if customers.empty:
        return {"customers": 0, "repeat_customers": 0, "repeat_rate_pct": 0.0,
                "avg_orders_per_customer": 0.0, "repeat_revenue_share_pct": 0.0}
    repeat = customers["orders"] >= 2
    total_revenue = customers["revenue"].sum()
    return {
        "customers": int(len(customers)),
        "repeat_customers": int(repeat.sum()),
        "repeat_rate_pct": float(repeat.mean() * 100),
        "avg_orders_per_customer": float(customers["orders"].mean()),
        "repeat_revenue_share_pct": float(
            customers.loc[repeat, "revenue"].sum() / total_revenue * 100
        ) if total_revenue else 0.0,
    }


def _score_1_to_5(values: pd.Series, higher_is_better: bool) -> pd.Series:
    """Tie-aware 1-5 score from the percentile rank (equal values get equal scores)."""
    signed = values if higher_is_better else -values
    percentile = signed.rank(pct=True, method="average")
    return np.ceil(percentile * 5).clip(1, 5).astype(int)


def rfm_segmentation(df: pd.DataFrame) -> pd.DataFrame:
    """Rule-based RFM (Recency, Frequency, Monetary) customer segments.

    This is a transparent business rule set, NOT machine learning.
    """
    cols = ["customer_id", "last_order", "recency_days", "frequency", "monetary",
            "r_score", "f_score", "m_score", "segment"]
    if df.empty:
        return pd.DataFrame(columns=cols)

    reference_date = df["order_date"].max().normalize() + pd.Timedelta(days=1)
    rfm = df.groupby("customer_id").agg(
        last_order=("order_date", "max"),
        frequency=("order_id", "nunique"),
        monetary=("revenue", "sum"),
    ).reset_index()
    rfm["recency_days"] = (reference_date - rfm["last_order"]).dt.days
    rfm["r_score"] = _score_1_to_5(rfm["recency_days"], higher_is_better=False)
    rfm["f_score"] = _score_1_to_5(rfm["frequency"], higher_is_better=True)
    rfm["m_score"] = _score_1_to_5(rfm["monetary"], higher_is_better=True)

    r = rfm["r_score"]
    value = (rfm["f_score"] + rfm["m_score"]) / 2
    rfm["segment"] = np.select(
        [
            (r >= 4) & (value >= 4),
            (r >= 3) & (value >= 3),
            (r <= 2) & (value >= 3),
            (r >= 4) & (value < 3),
            (r <= 2) & (value < 3),
        ],
        ["Champions", "Loyal Customers", "At Risk", "Recent / Low Spend", "Lost / Low Value"],
        default="Needs Attention",
    )
    return rfm[cols].sort_values("monetary", ascending=False).reset_index(drop=True)


def rfm_segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    if rfm.empty:
        return pd.DataFrame(columns=["segment", "customers", "revenue",
                                     "revenue_share_pct", "avg_recency_days", "avg_orders"])
    out = rfm.groupby("segment").agg(
        customers=("customer_id", "count"),
        revenue=("monetary", "sum"),
        avg_recency_days=("recency_days", "mean"),
        avg_orders=("frequency", "mean"),
    ).reset_index()
    out["revenue_share_pct"] = out["revenue"] / out["revenue"].sum() * 100
    out = out[["segment", "customers", "revenue", "revenue_share_pct",
               "avg_recency_days", "avg_orders"]]
    return out.sort_values("revenue", ascending=False).reset_index(drop=True)


# =============================================================================
# Forecasting (statistical, explainable: linear trend + monthly seasonality)
# =============================================================================
def _fit_and_predict(y: np.ndarray, months: np.ndarray, future_months: np.ndarray,
                     use_seasonality: bool):
    """Fit trend (+ seasonality) on y; return fitted values and future predictions."""
    n = len(y)
    t = np.arange(n)
    slope, intercept = np.polyfit(t, y, 1)
    trend = intercept + slope * t
    seasonal = pd.Series(0.0, index=range(1, 13))
    if use_seasonality:
        residual_by_month = pd.Series(y - trend).groupby(months).mean()
        seasonal.loc[residual_by_month.index] = residual_by_month - residual_by_month.mean()
    fitted = trend + seasonal.reindex(months).to_numpy()
    future_t = np.arange(n, n + len(future_months))
    future = intercept + slope * future_t + seasonal.reindex(future_months).to_numpy()
    return np.clip(fitted, 0, None), np.clip(future, 0, None)


def _error_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    mask = actual > 0
    mape = float(np.mean(np.abs(actual[mask] - predicted[mask]) / actual[mask]) * 100) \
        if mask.any() else float("nan")
    return {"mae": float(np.mean(np.abs(actual - predicted))), "mape": mape}


def forecast_revenue(monthly: pd.DataFrame, horizon: int = 6,
                     holdout: int = config.DEFAULT_HOLDOUT_MONTHS) -> dict:
    """Forecast monthly revenue; always backtested against a naive baseline.

    Method: linear trend + average monthly seasonality (seasonality only with 24+
    months). Backtest: train on all but the last `holdout` months, predict them,
    and compare the error with a seasonal-naive (same month last year) baseline.
    """
    result = {"available": False, "message": "", "method": "", "history": monthly,
              "forecast": None, "metrics": None}
    n = len(monthly)
    if n < config.MIN_FORECAST_MONTHS:
        result["message"] = (
            f"Need at least {config.MIN_FORECAST_MONTHS} complete months of data to forecast; "
            f"the current selection has {n}."
        )
        return result

    holdout = int(min(max(holdout, 1), config.MAX_HOLDOUT_MONTHS))
    y = monthly["revenue"].to_numpy(dtype=float)
    months = monthly["month"].dt.month.to_numpy()
    use_seasonality = n >= config.SEASONAL_MIN_MONTHS
    result["method"] = (
        "Linear trend + monthly seasonality" if use_seasonality
        else "Linear trend only (less than 24 months, seasonality not estimated)"
    )

    # ---- backtest ---------------------------------------------------------------
    if n >= holdout + config.MIN_FORECAST_MONTHS:
        split = n - holdout
        train_seasonal = split >= config.SEASONAL_MIN_MONTHS
        _, predicted = _fit_and_predict(y[:split], months[:split], months[split:],
                                        train_seasonal)
        actual = y[split:]
        baseline = np.array([y[split + i - 12] for i in range(holdout)])  # same month last year
        model_err, base_err = _error_metrics(actual, predicted), _error_metrics(actual, baseline)
        result["metrics"] = {
            "holdout_months": holdout,
            "model_mae": model_err["mae"], "model_mape": model_err["mape"],
            "baseline_mae": base_err["mae"], "baseline_mape": base_err["mape"],
            "beats_baseline": model_err["mae"] < base_err["mae"],
        }

    # ---- final forecast ------------------------------------------------------------
    last_month = monthly["month"].iloc[-1]
    future_index = pd.date_range(last_month + pd.offsets.MonthBegin(1),
                                 periods=int(horizon), freq="MS")
    fitted, future = _fit_and_predict(y, months, future_index.month.to_numpy(), use_seasonality)
    spread = 1.96 * float(np.std(y - fitted, ddof=1)) if n > 2 else 0.0
    result["forecast"] = pd.DataFrame({
        "month": future_index,
        "forecast": future,
        "lower": np.clip(future - spread, 0, None),
        "upper": future + spread,
    })
    result["available"] = True
    return result


# =============================================================================
# Insights and recommendations (every sentence is computed from the data)
# =============================================================================
def generate_insights(df: pd.DataFrame) -> dict:
    """Return {'findings': [...], 'recommendations': [...]} based only on `df`."""
    findings: list[str] = []
    recommendations: list[str] = []
    if df.empty:
        return {"findings": ["No data in the current selection."], "recommendations": []}

    kpis = calculate_kpis(df)
    start, end = df["order_date"].min().date(), df["order_date"].max().date()
    findings.append(
        f"Between {start} and {end} the selection generated "
        f"{format_currency(kpis['total_revenue'])} from {kpis['total_orders']:,} orders "
        f"(average order value {format_currency(kpis['average_order_value'])})."
    )

    categories = sales_by_dimension(df, "category")
    if len(categories) > 1:
        top = categories.iloc[0]
        findings.append(
            f"'{top['category']}' is the largest category with "
            f"{top['revenue_share_pct']:.1f}% of revenue."
        )

    pareto = pareto_analysis(df, "product")
    p = pareto_summary(pareto)
    if p["total_items"] > 1:
        findings.append(
            f"{p['core_items']} of {p['total_items']} products ({p['core_items_pct']:.0f}%) "
            f"account for {config.PARETO_THRESHOLD_PCT}% of revenue."
        )
        if p["core_items_pct"] <= 30:
            recommendations.append(
                "Revenue is concentrated in a few products: protect their stock and "
                "availability first, and review whether the long tail is worth its cost."
            )

    regions = sales_by_dimension(df, "region")
    if len(regions) > 1:
        best, worst = regions.iloc[0], regions.iloc[-1]
        findings.append(
            f"Region '{best['region']}' leads with {best['revenue_share_pct']:.1f}% of revenue; "
            f"'{worst['region']}' is lowest with {worst['revenue_share_pct']:.1f}%."
        )

    monthly = drop_incomplete_last_month(monthly_sales(df), df["order_date"].max())
    if len(monthly) >= 2 and monthly["mom_growth_pct"].iloc[-1] == monthly["mom_growth_pct"].iloc[-1]:
        findings.append(
            f"Last complete month ({monthly['month'].iloc[-1]:%b %Y}) revenue changed "
            f"{monthly['mom_growth_pct'].iloc[-1]:+.1f}% versus the previous month."
        )
    if len(monthly) >= 13 and monthly["yoy_growth_pct"].iloc[-1] == monthly["yoy_growth_pct"].iloc[-1]:
        findings.append(
            f"Compared with {monthly['month'].iloc[-13]:%b %Y}, revenue in "
            f"{monthly['month'].iloc[-1]:%b %Y} changed "
            f"{monthly['yoy_growth_pct'].iloc[-1]:+.1f}%."
        )

    if kpis["profit_margin_pct"] is not None:
        findings.append(
            f"Overall gross margin (revenue minus product cost) is "
            f"{kpis['profit_margin_pct']:.1f}% on rows with known cost."
        )
        if len(categories) > 1 and "margin_pct" in categories:
            valid = categories.dropna(subset=["margin_pct"])
            if len(valid) > 1:
                hi, lo = valid.loc[valid["margin_pct"].idxmax()], valid.loc[valid["margin_pct"].idxmin()]
                findings.append(
                    f"Margin is highest in '{hi['category']}' ({hi['margin_pct']:.1f}%) and "
                    f"lowest in '{lo['category']}' ({lo['margin_pct']:.1f}%)."
                )
                if lo["revenue_share_pct"] >= 15:
                    recommendations.append(
                        f"'{lo['category']}' has the lowest margin but "
                        f"{lo['revenue_share_pct']:.0f}% of revenue: review its pricing, "
                        f"discounts and supplier cost."
                    )

    if kpis["discount_rate_pct"] > 0:
        findings.append(f"Discounts reduced gross sales by {kpis['discount_rate_pct']:.1f}%.")

    repeat = repeat_purchase_metrics(df)
    findings.append(
        f"{repeat['repeat_rate_pct']:.1f}% of customers ordered more than once in this "
        f"selection; they contribute {repeat['repeat_revenue_share_pct']:.1f}% of revenue."
    )

    growth = period_growth_by_dimension(df, "product").dropna(subset=["growth_pct"])
    if len(growth) >= 2:
        up, down = growth.iloc[0], growth.iloc[-1]
        findings.append(
            f"Last 12 months vs the 12 before: fastest-growing product is '{up['product']}' "
            f"({up['growth_pct']:+.1f}%), steepest decline is '{down['product']}' "
            f"({down['growth_pct']:+.1f}%)."
        )
        if down["growth_pct"] < 0:
            recommendations.append(
                f"Investigate why '{down['product']}' declined {abs(down['growth_pct']):.0f}% "
                f"(pricing, stock-outs, competition) before deciding to keep or drop it."
            )

    rfm = rfm_segment_summary(rfm_segmentation(df))
    at_risk = rfm.loc[rfm["segment"] == "At Risk"]
    if not at_risk.empty and at_risk["customers"].iloc[0] > 0:
        row = at_risk.iloc[0]
        recommendations.append(
            f"{int(row['customers'])} 'At Risk' customers (good past value, not ordering "
            f"recently) hold {row['revenue_share_pct']:.1f}% of revenue: consider a win-back offer."
        )

    findings.append("These are descriptive findings; they show what happened, not why.")
    return {"findings": findings, "recommendations": recommendations}
