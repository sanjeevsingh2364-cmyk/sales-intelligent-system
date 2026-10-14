"""
Data cleaning: raw text table  ->  typed, validated, analysis-ready table.

Philosophy: never delete silently. Every removed or repaired row is counted in a
report that the dashboard shows on the "Data Quality" tab.

Assumptions (also documented in the README):
  * One row = one product line of an order (order_id may repeat across rows).
  * `discount` is a FRACTION between 0 and 1 (0.10 = 10%). Other values are invalid.
  * Non-ISO dates (e.g. 03/04/2024) are read month-first. ISO (YYYY-MM-DD) is safest.
  * Two rows that are identical in every column are treated as duplicates.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config


def _parse_dates(series: pd.Series) -> pd.Series:
    """Parse ISO dates first, then fall back to mixed formats for the leftovers."""
    text = series.astype("string").str.strip()
    parsed = pd.to_datetime(text, format="ISO8601", errors="coerce")
    leftover = parsed.isna() & text.notna()
    if leftover.any():
        parsed.loc[leftover] = pd.to_datetime(
            text[leftover], format="mixed", dayfirst=False, errors="coerce"
        )
    return parsed


def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Return (clean_df, report). `raw` must already have validated columns."""
    df = raw.copy()
    report: dict = {"rows_input": int(len(df)), "removed": {}, "filled": {}, "notes": []}

    def drop_rows(mask: pd.Series, reason: str) -> None:
        nonlocal df
        count = int(mask.sum())
        if count:
            report["removed"][reason] = count
        df = df.loc[~mask].copy()

    # 1. Text columns: trim, collapse spaces, empty -> missing ------------------
    for col in config.TEXT_COLUMNS:
        text = df[col].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
        df[col] = text.replace("", pd.NA)
    df["region"] = df["region"].str.title()
    df["category"] = df["category"].str.title()

    # 2. Type conversion ----------------------------------------------------------
    df["order_date"] = _parse_dates(df["order_date"])
    for col in ["quantity", "unit_price", "discount", "unit_cost"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 3. Remove rows that cannot be trusted ---------------------------------------
    key_cols = ["order_id", "customer_id", "product", "category"]
    drop_rows(df[key_cols].isna().any(axis=1), "missing_order_customer_product_or_category")
    drop_rows(df["order_date"].isna(), "invalid_or_missing_date")
    drop_rows(df["order_date"] > pd.Timestamp.today() + pd.Timedelta(days=1), "future_date")
    drop_rows(df["quantity"].isna() | (df["quantity"] <= 0), "invalid_quantity")
    drop_rows(df["unit_price"].isna() | (df["unit_price"] <= 0), "invalid_unit_price")

    # 4. Optional columns ---------------------------------------------------------
    if "discount" in df.columns:
        drop_rows(df["discount"].notna() & ((df["discount"] < 0) | (df["discount"] > 1)),
                  "discount_outside_0_to_1")
        missing_discount = int(df["discount"].isna().sum())
        if missing_discount:
            report["filled"]["missing_discount_set_to_0"] = missing_discount
        df["discount"] = df["discount"].fillna(0.0)
    else:
        df["discount"] = 0.0
        report["notes"].append("No 'discount' column found: discount assumed to be 0.")

    if "unit_cost" in df.columns:
        negative_cost = df["unit_cost"] < 0
        if negative_cost.any():
            report["filled"]["negative_unit_cost_set_to_missing"] = int(negative_cost.sum())
        df.loc[negative_cost, "unit_cost"] = np.nan
    else:
        df["unit_cost"] = np.nan
        report["notes"].append("No 'unit_cost' column found: profit analysis is disabled.")

    # 5. Repair, do not delete: missing region -> 'Unknown' ------------------------
    missing_region = int(df["region"].isna().sum())
    if missing_region:
        report["filled"]["missing_region_set_to_Unknown"] = missing_region
    df["region"] = df["region"].fillna("Unknown")

    # 6. Exact duplicates ------------------------------------------------------------
    drop_rows(df.duplicated(keep="first"), "duplicate_rows")

    # 7. Derived business columns ----------------------------------------------------
    if (df["quantity"] % 1 == 0).all():
        df["quantity"] = df["quantity"].astype("int64")
    df["gross_sales"] = df["quantity"] * df["unit_price"]
    df["discount_amount"] = df["gross_sales"] * df["discount"]
    df["revenue"] = df["gross_sales"] - df["discount_amount"]
    df["total_cost"] = df["quantity"] * df["unit_cost"]               # NaN if cost unknown
    df["profit"] = df["revenue"] - df["total_cost"]                   # NaN if cost unknown
    df["revenue_costed"] = df["revenue"].where(df["profit"].notna())  # base for margin %
    df["month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
    df["year"] = df["order_date"].dt.year.astype("int64")
    df["quarter"] = df["year"].astype(str) + "-Q" + df["order_date"].dt.quarter.astype(str)

    for col in config.TEXT_COLUMNS:
        df[col] = df[col].astype(object)

    df = df.sort_values(["order_date", "order_id"]).reset_index(drop=True)

    report["rows_output"] = int(len(df))
    report["rows_removed_total"] = report["rows_input"] - report["rows_output"]
    report["has_profit_data"] = bool(df["profit"].notna().any())
    return df, report
