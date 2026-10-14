"""Shared test data: a tiny dataset whose correct answers are computed BY HAND."""
import pandas as pd

from src.data_cleaning import clean_data

# order  customer region  category    product  qty price disc  cost  -> revenue / profit
# O1 2024-01-10 C1 North Tech   Laptop  2 100 0.0 60 -> 200 / 80
# O1 2024-01-10 C1 North Tech   Mouse   1  50 0.1 20 ->  45 / 25
# O2 2024-02-15 C2 South Furn   Chair   1 200 0.0 120-> 200 / 80
# O3 2024-03-20 C1 North Furn   Desk    3 100 0.5 40 -> 150 / 30
# Hand-computed: revenue 595 | orders 3 | units 7 | AOV 595/3 | profit 215 | customers 2
ROWS = [
    ("O1", "2024-01-10", "C1", "North", "Tech", "Laptop", 2, 100, 0.0, 60),
    ("O1", "2024-01-10", "C1", "North", "Tech", "Mouse", 1, 50, 0.1, 20),
    ("O2", "2024-02-15", "C2", "South", "Furn", "Chair", 1, 200, 0.0, 120),
    ("O3", "2024-03-20", "C1", "North", "Furn", "Desk", 3, 100, 0.5, 40),
]
COLUMNS = ["order_id", "order_date", "customer_id", "region", "category", "product",
           "quantity", "unit_price", "discount", "unit_cost"]


def raw_frame(rows=ROWS) -> pd.DataFrame:
    """Raw (text) frame exactly like data_loader would return."""
    return pd.DataFrame(rows, columns=COLUMNS).astype(str)


def clean_frame(rows=ROWS) -> pd.DataFrame:
    return clean_data(raw_frame(rows))[0]


def two_year_rows():
    """Jan 2023 .. Feb 2024, one order per month: 100 in 2023, 150 in 2024."""
    rows = []
    for i, month in enumerate(pd.date_range("2023-01-01", "2024-02-01", freq="MS")):
        price = 100 if month.year == 2023 else 150
        rows.append((f"X{i}", month.strftime("%Y-%m-15"), f"C{i % 3}", "North", "Tech",
                     "Laptop", 1, price, 0.0, 50))
    return rows
