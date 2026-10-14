"""
Central configuration for the Sales Intelligent System.

Every path, column name and business constant lives here so that the other
modules never hardcode them. Change a value once, and the whole project follows.
"""

from pathlib import Path

# ----------------------------------------------------------------------------
# Paths (always relative to this file, so the project runs from any location)
# ----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"

# The synthetic file name contains the word SYNTHETIC on purpose.
SAMPLE_DATA_PATH = DATA_RAW_DIR / "sample_sales_SYNTHETIC.csv"
PROCESSED_DATA_PATH = DATA_PROCESSED_DIR / "clean_sales.csv"
CLEANING_REPORT_PATH = DATA_PROCESSED_DIR / "cleaning_report.json"

# ----------------------------------------------------------------------------
# Dataset schema (one row = one product line inside an order)
# ----------------------------------------------------------------------------
REQUIRED_COLUMNS = [
    "order_id",
    "order_date",
    "customer_id",
    "region",
    "category",
    "product",
    "quantity",
    "unit_price",
]
# Optional: if missing, the system still works (profit analysis is skipped).
OPTIONAL_COLUMNS = ["discount", "unit_cost"]
TEXT_COLUMNS = ["order_id", "customer_id", "region", "category", "product"]

# ----------------------------------------------------------------------------
# Business constants
# ----------------------------------------------------------------------------
CURRENCY_SYMBOL = "₹"          # change to "$" etc. if your data uses another currency
PARETO_THRESHOLD_PCT = 80      # "core contributors" make up the first 80% of revenue
MIN_FORECAST_MONTHS = 12       # below this we refuse to forecast
SEASONAL_MIN_MONTHS = 24       # need 2 full years to estimate seasonality
MAX_HOLDOUT_MONTHS = 12
DEFAULT_HOLDOUT_MONTHS = 6
GROWTH_WINDOW_DAYS = 365       # "last 12 months vs previous 12 months"
