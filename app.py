
"""
Sales Intelligent System - Streamlit dashboard.

Run from the project root:
    python -m streamlit run app.py

This file only handles the user interface. All calculations live in src/analytics.py,
all charts in src/visualizations.py, all cleaning in src/data_cleaning.py.
"""

from __future__ import annotations

import io


import pandas as pd
import streamlit as st

import config
from src import analytics, exporter
from src import visualizations as viz
from src.data_loader import DataValidationError
from src.generate_sample_data import generate_sales_data
from src.pipeline import load_and_clean

st.set_page_config(page_title="Sales Intelligent System", page_icon="📊", layout="wide")

SAMPLE_LABEL = "Synthetic sample data (demo)"
UPLOAD_LABEL = "Upload my own CSV / Excel"

LABELS = {
    "revenue": "Revenue", "units": "Units", "orders": "Orders", "profit": "Profit",
    "margin_pct": "Margin %", "revenue_share_pct": "Share of revenue %",
    "avg_order_value": "Avg order value", "growth_pct": "Growth %",
    "recent_revenue": "Last 12 months", "prior_revenue": "Previous 12 months",
    "cumulative_share_pct": "Cumulative %", "is_core_contributor": "Core (top 80%)",
    "customer_id": "Customer", "last_order": "Last order", "first_order": "First order",
    "recency_days": "Days since last order", "frequency": "Orders", "monetary": "Revenue",
    "avg_recency_days": "Avg days since last order", "avg_orders": "Avg orders",
    "category": "Category", "product": "Product", "region": "Region",
    "quarter": "Quarter", "year": "Year", "segment": "Segment", "customers": "Customers",
}


# -----------------------------------------------------------------------------
# Data loading (cached, so filter clicks do not re-read the file)
# -----------------------------------------------------------------------------
def ensure_sample_file() -> None:
    """Create the SYNTHETIC sample CSV on first run."""
    if not config.SAMPLE_DATA_PATH.exists():
        config.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
        generate_sales_data().to_csv(config.SAMPLE_DATA_PATH, index=False)


@st.cache_data(show_spinner="Loading and cleaning data...")
def get_clean_data(file_bytes: bytes | None, filename: str | None, use_sample: bool):
    if use_sample:
        ensure_sample_file()
        return load_and_clean(config.SAMPLE_DATA_PATH)
    return load_and_clean(io.BytesIO(file_bytes), filename=filename)


def show_table(table: pd.DataFrame, decimals: int = 1) -> None:
    shown = table.copy()
    numeric_cols = shown.select_dtypes("number").columns   # never round dates/text
    shown[numeric_cols] = shown[numeric_cols].round(decimals)
    st.dataframe(shown.rename(columns=LABELS), hide_index=True)


def money(value) -> str:
    return "N/A" if value is None else analytics.format_currency(value)


# -----------------------------------------------------------------------------
# Sidebar: data source
# -----------------------------------------------------------------------------
st.sidebar.title("📊 Sales Intelligence")
source_choice = st.sidebar.radio("Data source", [SAMPLE_LABEL, UPLOAD_LABEL])
uploaded = None
if source_choice == UPLOAD_LABEL:
    uploaded = st.sidebar.file_uploader("CSV or Excel (.xlsx)", type=["csv", "xlsx"])
    if uploaded is None:
        st.title("📊 Sales Intelligent System")
        st.info("Upload a file to begin. Required columns: "
                + ", ".join(f"`{c}`" for c in config.REQUIRED_COLUMNS)
                + ". Optional: " + ", ".join(f"`{c}`" for c in config.OPTIONAL_COLUMNS) + ".")
        st.stop()

is_synthetic = uploaded is None
try:
    if is_synthetic:
        clean_df, report = get_clean_data(None, None, True)
    else:
        clean_df, report = get_clean_data(uploaded.getvalue(), uploaded.name, False)
except DataValidationError as exc:
    st.title("📊 Sales Intelligent System")
    st.error(f"Could not use this file. {exc}")
    st.stop()

if clean_df.empty:
    st.error("No valid rows remain after cleaning. Open the file and check dates, "
             "quantities and prices.")
    st.stop()

# -----------------------------------------------------------------------------
# Sidebar: filters
# -----------------------------------------------------------------------------
st.sidebar.header("Filters")
min_date, max_date = clean_df["order_date"].min().date(), clean_df["order_date"].max().date()
date_range = st.sidebar.date_input("Order date range", value=(min_date, max_date),
                                   min_value=min_date, max_value=max_date)
if not (isinstance(date_range, (tuple, list)) and len(date_range) == 2):
    st.info("Please pick both a start date and an end date.")
    st.stop()
start_date, end_date = date_range

all_regions = sorted(clean_df["region"].unique())
all_categories = sorted(clean_df["category"].unique())
sel_regions = st.sidebar.multiselect("Region", all_regions, default=all_regions)
sel_categories = st.sidebar.multiselect("Category", all_categories, default=all_categories)
product_options = sorted(
    clean_df.loc[clean_df["category"].isin(sel_categories), "product"].unique()
)
sel_products = st.sidebar.multiselect("Product", product_options, default=product_options)

filters_text = (
    f"{start_date} to {end_date}; regions: {len(sel_regions)}/{len(all_regions)}; "
    f"categories: {len(sel_categories)}/{len(all_categories)}; "
    f"products: {len(sel_products)}/{len(product_options)}"
)
filtered = analytics.apply_filters(clean_df, start_date, end_date,
                                   sel_regions, sel_categories, sel_products)

# -----------------------------------------------------------------------------
# Header + KPIs
# -----------------------------------------------------------------------------
st.title("📊 Sales Intelligent System")
if is_synthetic:
    st.warning("⚠️ **SYNTHETIC SAMPLE DATA.** All numbers are artificially generated for "
               "demonstration. They are NOT real business results.")

if filtered.empty:
    st.warning("No rows match the current filters. Widen the date range or select at "
               "least one region, category and product.")
    st.stop()

kpis = analytics.calculate_kpis(filtered)
row1 = st.columns(4)
row1[0].metric("Total revenue", money(kpis["total_revenue"]))
row1[1].metric("Orders (distinct)", f"{kpis['total_orders']:,}")
row1[2].metric("Units sold", f"{kpis['total_units']:,.0f}")
row1[3].metric("Avg order value", money(kpis["average_order_value"]))
row2 = st.columns(4)
row2[0].metric("Customers", f"{kpis['unique_customers']:,}")
row2[1].metric("Discount rate", f"{kpis['discount_rate_pct']:.1f}%")
row2[2].metric("Gross profit", money(kpis["gross_profit"]))
row2[3].metric("Gross margin",
               "N/A" if kpis["profit_margin_pct"] is None else f"{kpis['profit_margin_pct']:.1f}%")

monthly = analytics.monthly_sales(filtered)
categories = analytics.sales_by_dimension(filtered, "category")
products = analytics.sales_by_dimension(filtered, "product")
regions = analytics.sales_by_dimension(filtered, "region")

tabs = st.tabs(["Overview", "Products & Categories", "Regions & Customers",
                "Trends & Growth", "Forecast", "Insights", "Data & Export", "Data Quality"])

# ------------------------------- Overview -------------------------------------
with tabs[0]:
    left, right = st.columns([3, 2])
    left.plotly_chart(viz.revenue_trend_chart(monthly))
    right.plotly_chart(viz.donut_chart(categories, "category", "revenue", "Revenue by category"))
    st.subheader("Quarterly performance")
    show_table(analytics.sales_by_period(filtered, "quarter"))
    st.caption("First and last quarter may be partial depending on the date range.")

# --------------------------- Products & Categories ------------------------------
with tabs[1]:
    c1, c2 = st.columns(2)
    c1.plotly_chart(viz.bar_chart(categories, "category", "revenue", "Revenue by category"))
    if "margin_pct" in categories:
        c2.plotly_chart(viz.bar_chart(categories.dropna(subset=["margin_pct"]), "category",
                                      "margin_pct", "Gross margin % by category", color="#2ca02c"))
    else:
        c2.info("Margin chart needs a `unit_cost` column.")

    st.subheader("Product performance")
    top_n = st.slider("Number of products to show", 3, max(3, len(products)), min(10, len(products)))
    st.plotly_chart(viz.bar_chart(products.head(top_n), "product", "revenue",
                                  f"Top {top_n} products by revenue"))
    top5, bottom5 = analytics.top_and_bottom(filtered, "product", 5)
    t1, t2 = st.columns(2)
    t1.markdown("**Top 5 products**")
    with t1:
        show_table(top5)
    t2.markdown("**Bottom 5 products**")
    with t2:
        show_table(bottom5)

    st.subheader("Pareto (80/20) analysis")
    pareto = analytics.pareto_analysis(filtered, "product")
    summary = analytics.pareto_summary(pareto)
    st.write(f"**{summary['core_items']} of {summary['total_items']} products "
             f"({summary['core_items_pct']:.0f}%)** generate {config.PARETO_THRESHOLD_PCT}% "
             f"of revenue.")
    st.plotly_chart(viz.pareto_chart(pareto, "product"))

    st.subheader("Growth: last 12 months vs previous 12 months")
    growth = analytics.period_growth_by_dimension(filtered, "product")
    if growth.empty:
        st.info("Needs at least 24 months of data in the selected date range.")
    else:
        show_table(growth)

# --------------------------- Regions & Customers ---------------------------------
with tabs[2]:
    r1, r2 = st.columns(2)
    r1.plotly_chart(viz.bar_chart(regions, "region", "revenue", "Revenue by region"))
    with r2:
        show_table(regions)

    st.subheader("Repeat purchase behaviour")
    repeat = analytics.repeat_purchase_metrics(filtered)
    m = st.columns(4)
    m[0].metric("Customers", f"{repeat['customers']:,}")
    m[1].metric("Repeat customers", f"{repeat['repeat_customers']:,}")
    m[2].metric("Repeat rate", f"{repeat['repeat_rate_pct']:.1f}%")
    m[3].metric("Revenue from repeat customers", f"{repeat['repeat_revenue_share_pct']:.1f}%")
    st.caption("Repeat = 2+ distinct orders inside the selected filters. A customer with "
               "one order here may have ordered more outside the selection.")

    st.subheader("Customer segments (rule-based RFM)")
    rfm = analytics.rfm_segmentation(filtered)
    seg = analytics.rfm_segment_summary(rfm)
    s1, s2 = st.columns(2)
    s1.plotly_chart(viz.bar_chart(seg, "segment", "customers", "Customers per segment"))
    with s2:
        show_table(seg)
    st.markdown("**Top 10 customers by revenue**")
    show_table(analytics.customer_summary(filtered).head(10))

# ------------------------------ Trends & Growth ----------------------------------

with tabs[3]:
    st.plotly_chart(
        viz.revenue_trend_chart(monthly),
        key="trends_revenue_chart",
        use_container_width=True
    )

    metric_label = st.radio(
        "Growth metric",
        ["Month-over-month", "Year-over-year"],
        horizontal=True
    )

    metric = (
        "mom_growth_pct"
        if metric_label == "Month-over-month"
        else "yoy_growth_pct"
    )

    if monthly[metric].notna().any():
        st.plotly_chart(
            viz.growth_chart(monthly, metric),
            key="trends_growth_chart",
            use_container_width=True
        )
    else:
        st.info(
            "Not enough history for this growth metric "
            "in the selected range."
        )

    st.plotly_chart(
        viz.seasonality_heatmap(monthly),
        key="trends_seasonality_chart",
        use_container_width=True
    )

    period = st.selectbox(
        "Aggregate by",
        ["quarter", "year"]
    )

    show_table(analytics.sales_by_period(filtered, period))

    st.caption(
        "A partial first/last period (for example the current year) "
        "will look like a decline. Check the date range before drawing conclusions."
    )


# --------------------------------- Forecast ---------------------------------------
with tabs[4]:
    st.markdown("Statistical forecast of **monthly revenue** (linear trend + monthly "
                "seasonality), checked against a simple baseline.")
    horizon = st.slider("Months to forecast", 3, 12, 6)
    complete = analytics.drop_incomplete_last_month(monthly, filtered["order_date"].max())
    result = analytics.forecast_revenue(complete, horizon=horizon)
    if not result["available"]:
        st.info(result["message"])
    else:
        st.caption(f"Method: {result['method']}  |  History used: {len(complete)} complete months")
        st.plotly_chart(viz.forecast_chart(result["history"], result["forecast"]))
        metrics = result["metrics"]
        if metrics:
            f1, f2, f3 = st.columns(3)
            f1.metric(f"Model error (MAPE, last {metrics['holdout_months']} months)",
                      f"{metrics['model_mape']:.1f}%")
            f2.metric("Baseline error (same month last year)", f"{metrics['baseline_mape']:.1f}%")
            f3.metric("Beats baseline?", "Yes" if metrics["beats_baseline"] else "No")
            if not metrics["beats_baseline"]:
                st.warning("The model did not beat the simple baseline on the backtest. "
                           "Treat this forecast with extra caution.")
        else:
            st.info("Not enough history for a backtest, so accuracy is unknown.")
        show_table(result["forecast"].assign(month=lambda d: d["month"].dt.strftime("%b %Y")), 0)
        with st.expander("Limitations of this forecast"):
            st.markdown(
                "- Assumes past trend and seasonality continue; it cannot see promotions, "
                "price changes or market shocks.\n"
                "- The shaded range is approximate (based on in-sample error) and is likely "
                "too narrow.\n- With only 2-3 years of history, seasonality estimates are rough.\n"
                "- Forecast uses the *filtered* data, so it changes with your filters."
            )

# --------------------------------- Insights ---------------------------------------
with tabs[5]:
    insights = analytics.generate_insights(filtered)
    st.subheader("Findings")
    for line in insights["findings"]:
        st.markdown(f"- {line}")
    st.subheader("Suggested actions")
    if insights["recommendations"]:
        for line in insights["recommendations"]:
            st.markdown(f"- {line}")
    else:
        st.write("No rule-based recommendation was triggered for this selection.")
    st.caption("Every sentence above is computed from the current selection by "
               "rule-based logic. It describes patterns, not causes.")

# ------------------------------- Data & Export -------------------------------------
with tabs[6]:
    st.write(f"Filtered rows: **{len(filtered):,}** of {len(clean_df):,} clean rows")
    st.dataframe(filtered.drop(columns=["revenue_costed"]).head(500), hide_index=True)
    st.caption("Preview shows the first 500 rows. Downloads contain all filtered rows.")
    stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M")
    tag = "SYNTHETIC_" if is_synthetic else ""
    st.download_button("⬇️ Download filtered data (CSV)",
                       exporter.dataframe_to_csv_bytes(filtered.drop(columns=["revenue_costed"])),
                       file_name=f"{tag}sales_filtered_{stamp}.csv", mime="text/csv")

    signature = (filters_text, len(filtered), round(kpis["total_revenue"], 2), is_synthetic)
    if st.button("Prepare Excel report"):
        st.session_state["excel"] = (
            signature, exporter.build_excel_report(filtered, filters_text, is_synthetic))
    cached = st.session_state.get("excel")
    if cached and cached[0] == signature:
        st.download_button(
            "⬇️ Download Excel report", cached[1],
            file_name=f"{tag}sales_report_{stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    elif cached:
        st.info("Filters changed since the report was prepared. Click 'Prepare Excel report' again.")

# ------------------------------- Data Quality --------------------------------------
with tabs[7]:
    q = st.columns(3)
    q[0].metric("Rows in file", f"{report['rows_input']:,}")
    q[1].metric("Rows after cleaning", f"{report['rows_output']:,}")
    q[2].metric("Rows removed", f"{report['rows_removed_total']:,}")
    if report["removed"]:
        st.markdown("**Removed rows by reason**")
        st.dataframe(pd.DataFrame(report["removed"].items(), columns=["Reason", "Rows"]),
                     hide_index=True)
    if report["filled"]:
        st.markdown("**Repaired values**")
        st.dataframe(pd.DataFrame(report["filled"].items(), columns=["Repair", "Rows"]),
                     hide_index=True)
    for note in report["notes"]:
        st.info(note)
    if not report["removed"] and not report["filled"]:
        st.success("No data quality problems were found.")
