"""Export helpers: filtered CSV and a multi-sheet Excel report (openpyxl)."""

from __future__ import annotations

import io
from datetime import datetime

import pandas as pd

from src import analytics

SYNTHETIC_NOTE = "SYNTHETIC SAMPLE DATA - artificial numbers, not real business results."


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """UTF-8 with BOM so that Excel opens special characters correctly."""
    return df.to_csv(index=False).encode("utf-8-sig")


def _autofit(worksheet) -> None:
    for column_cells in worksheet.columns:
        longest = max((len(str(c.value)) for c in column_cells if c.value is not None), default=8)
        worksheet.column_dimensions[column_cells[0].column_letter].width = min(longest + 2, 45)


def build_excel_report(df: pd.DataFrame, filters_text: str, is_synthetic: bool = False,
                       report_date: datetime | None = None) -> bytes:
    """Excel workbook: Summary, By Category, By Product, By Region, Monthly, Filtered Data."""
    report_date = report_date or datetime.now()
    kpis = analytics.calculate_kpis(df)

    def show(value, money=False):
        if value is None:
            return "N/A (no cost data)"
        return round(value, 2) if not money else round(value, 2)

    summary_rows = [
        ("Report date", report_date.strftime("%Y-%m-%d %H:%M")),
        ("Filters applied", filters_text),
        ("Data source", SYNTHETIC_NOTE if is_synthetic else "User-provided data"),
        ("", ""),
        ("Total revenue", show(kpis["total_revenue"])),
        ("Total orders (distinct)", kpis["total_orders"]),
        ("Total units", kpis["total_units"]),
        ("Average order value", show(kpis["average_order_value"])),
        ("Unique customers", kpis["unique_customers"]),
        ("Discount rate %", show(kpis["discount_rate_pct"])),
        ("Gross profit", show(kpis["gross_profit"])),
        ("Gross margin %", show(kpis["profit_margin_pct"])),
    ]
    summary = pd.DataFrame(summary_rows, columns=["Metric", "Value"])
    export_cols = [c for c in df.columns if c not in ("revenue_costed",)]
    data = df[export_cols].copy()

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        sheets = {
            "Summary": summary,
            "By Category": analytics.sales_by_dimension(df, "category"),
            "By Product": analytics.sales_by_dimension(df, "product"),
            "By Region": analytics.sales_by_dimension(df, "region"),
            "Monthly": analytics.monthly_sales(df),
            "Filtered Data": data,
        }
        for name, table in sheets.items():
            table.to_excel(writer, sheet_name=name, index=False)
            _autofit(writer.sheets[name])
    return buffer.getvalue()
