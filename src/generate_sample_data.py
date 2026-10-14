"""
SYNTHETIC sales data generator.

!!! WARNING !!!
Everything produced here is RANDOM, ARTIFICIAL data created only so that the
project can be developed and demonstrated. It does NOT describe any real
business. Never present results from this data as real business results.

Run from the project root:
    python -m src.generate_sample_data
    python -m src.generate_sample_data --clean          (no deliberately dirty rows)
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

import config

# category -> list of (product, base_price, cost_ratio). cost = price * ratio.
CATALOG: dict[str, list[tuple[str, float, float]]] = {
    "Electronics": [
        ("Laptop", 55000, 0.78),
        ("Smartphone", 28000, 0.80),
        ("Headphones", 3500, 0.55),
        ("Smartwatch", 9000, 0.65),
    ],
    "Furniture": [
        ("Office Chair", 7500, 0.60),
        ("Study Desk", 9500, 0.62),
        ("Bookshelf", 6200, 0.58),
        ("Sofa Set", 32000, 0.70),
    ],
    "Office Supplies": [
        ("Notebook Pack", 350, 0.45),
        ("Printer Paper", 450, 0.70),
        ("Ink Cartridge", 1800, 0.60),
        ("Desk Organizer", 650, 0.50),
    ],
    "Clothing": [
        ("Formal Shirt", 1800, 0.50),
        ("Denim Jeans", 2200, 0.52),
        ("Winter Jacket", 4800, 0.58),
        ("Running Shoes", 3600, 0.55),
    ],
}

REGIONS = ["North", "South", "East", "West", "Central"]
REGION_WEIGHTS = [0.25, 0.30, 0.15, 0.20, 0.10]


def _daily_probabilities(days: pd.DatetimeIndex) -> np.ndarray:
    """Probability of an order on each day: growth + seasonality + weekends."""
    t = np.arange(len(days))
    growth = 1 + 0.5 * t / len(days)                       # business slowly grows
    day_of_year = days.dayofyear.to_numpy()
    seasonal = 1 + 0.20 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
    festive = np.where(days.month.isin([10, 11]), 1.35, 1.0)  # Oct/Nov festive boost
    weekend = np.where(days.dayofweek >= 5, 1.15, 1.0)
    weights = growth * seasonal * festive * weekend
    return weights / weights.sum()


def generate_sales_data(
    n_orders: int = 8000,
    n_customers: int = 800,
    start: str = "2022-01-01",
    end: str = "2024-12-31",
    seed: int = 42,
    add_dirty_rows: bool = True,
) -> pd.DataFrame:
    """Return a synthetic sales DataFrame (deterministic for a given seed)."""
    rng = np.random.default_rng(seed)

    # --- products -----------------------------------------------------------
    products = [
        (cat, name, price, ratio)
        for cat, items in CATALOG.items()
        for name, price, ratio in items
    ]
    # Cheaper items sell more often; random popularity makes a Pareto-like shape.
    prices = np.array([p[2] for p in products])
    popularity = rng.lognormal(mean=0.0, sigma=0.6, size=len(products)) / prices**0.25
    popularity = popularity / popularity.sum()

    # --- customers (each customer belongs to one region) --------------------
    customer_ids = np.array([f"C{i:04d}" for i in range(1, n_customers + 1)])
    customer_region = rng.choice(REGIONS, size=n_customers, p=REGION_WEIGHTS)
    activity = rng.gamma(shape=0.8, scale=1.0, size=n_customers) + 0.05
    activity = activity / activity.sum()

    # --- order level data ---------------------------------------------------
    days = pd.date_range(start, end, freq="D")
    order_days = rng.choice(len(days), size=n_orders, p=_daily_probabilities(days))
    order_customers = rng.choice(n_customers, size=n_orders, p=activity)
    discount_choices = np.array([0, 0, 0, 0, 0.05, 0.10, 0.15, 0.20])

    rows = []
    for i in range(n_orders):
        c_idx = order_customers[i]
        n_lines = rng.choice([1, 2, 3, 4], p=[0.50, 0.30, 0.15, 0.05])
        line_products = rng.choice(len(products), size=n_lines, replace=False, p=popularity)
        discount = float(rng.choice(discount_choices))
        for p_idx in line_products:
            category, name, base_price, cost_ratio = products[p_idx]
            lam = 0.3 if base_price > 20000 else 1.2
            rows.append(
                {
                    "order_id": f"O{i + 1:06d}",
                    "order_date": days[order_days[i]].strftime("%Y-%m-%d"),
                    "customer_id": customer_ids[c_idx],
                    "region": customer_region[c_idx],
                    "category": category,
                    "product": name,
                    "quantity": int(1 + rng.poisson(lam)),
                    "unit_price": round(base_price * rng.uniform(0.97, 1.03), 2),
                    "discount": discount,
                    "unit_cost": round(base_price * cost_ratio * rng.uniform(0.98, 1.02), 2),
                }
            )

    df = pd.DataFrame(rows)
    if add_dirty_rows:
        df = _inject_dirty_rows(df, rng)
    return df


def _inject_dirty_rows(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Deliberately damage a tiny share of rows so the cleaning step has work to do."""
    n = len(df)
    duplicates = df.iloc[rng.choice(n, size=int(0.006 * n), replace=False)].copy()

    df = df.copy()
    perm = rng.permutation(n)

    def take(share: float, start: int) -> tuple[np.ndarray, int]:
        size = int(share * n)
        return perm[start : start + size], start + size

    idx_region, a = take(0.005, 0)
    idx_text, a = take(0.010, a)
    idx_date, a = take(0.002, a)
    idx_qty, a = take(0.002, a)
    idx_price, a = take(0.002, a)

    df.loc[df.index[idx_region], "region"] = None
    df.loc[df.index[idx_text], "category"] = df.loc[df.index[idx_text], "category"].str.upper()
    df.loc[df.index[idx_text], "region"] = (
        " " + df.loc[df.index[idx_text], "region"].str.lower() + " "
    )
    df.loc[df.index[idx_date], "order_date"] = "not a date"
    df.loc[df.index[idx_qty], "quantity"] = -df.loc[df.index[idx_qty], "quantity"]
    df["unit_price"] = df["unit_price"].astype(float)
    df.loc[df.index[idx_price], "unit_price"] = np.nan

    combined = pd.concat([df, duplicates], ignore_index=True)
    return combined.iloc[rng.permutation(len(combined))].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SYNTHETIC sales data.")
    parser.add_argument("--orders", type=int, default=8000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--clean", action="store_true", help="do not add dirty rows")
    parser.add_argument("--output", default=str(config.SAMPLE_DATA_PATH))
    args = parser.parse_args()

    df = generate_sales_data(n_orders=args.orders, seed=args.seed, add_dirty_rows=not args.clean)
    config.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"SYNTHETIC data written: {args.output}  ({len(df):,} rows)")
    print("Reminder: this is artificial data, not real business data.")


if __name__ == "__main__":
    main()
