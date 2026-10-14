"""Tests for the generator, loader and cleaning steps."""
import io
import unittest

import pandas as pd

from src.data_cleaning import clean_data
from src.data_loader import DataValidationError, load_data, normalise_column_names
from src.generate_sample_data import generate_sales_data
from tests.helpers import COLUMNS, ROWS, clean_frame, raw_frame


class LoaderTests(unittest.TestCase):
    def test_missing_required_column_raises_helpful_error(self):
        csv = io.BytesIO(b"order_id,order_date\nO1,2024-01-01\n")
        with self.assertRaises(DataValidationError) as ctx:
            load_data(csv, filename="x.csv")
        self.assertIn("Missing required column", str(ctx.exception))

    def test_unsupported_extension(self):
        with self.assertRaises(DataValidationError):
            load_data(io.BytesIO(b"abc"), filename="data.txt")

    def test_missing_file(self):
        with self.assertRaises(DataValidationError):
            load_data("definitely_not_here.csv")

    def test_empty_file(self):
        with self.assertRaises(DataValidationError):
            load_data(io.BytesIO(b""), filename="empty.csv")

    def test_column_names_are_normalised(self):
        df = pd.DataFrame(columns=[" Order Date ", "Unit-Price"])
        self.assertEqual(list(normalise_column_names(df).columns), ["order_date", "unit_price"])

    def test_valid_csv_loads_as_text(self):
        buf = io.BytesIO(raw_frame().to_csv(index=False).encode())
        df = load_data(buf, filename="ok.csv")
        self.assertEqual(len(df), len(ROWS))
        self.assertTrue(set(COLUMNS).issubset(df.columns))


class CleaningTests(unittest.TestCase):
    def test_revenue_and_profit_formulas(self):
        df = clean_frame()
        self.assertAlmostEqual(df["revenue"].sum(), 595.0)
        self.assertAlmostEqual(df["profit"].sum(), 215.0)

    def test_invalid_rows_are_removed_and_counted(self):
        rows = list(ROWS) + [
            ("O9", "not a date", "C1", "North", "Tech", "Laptop", 1, 100, 0.0, 60),
            ("O10", "2024-01-01", "C1", "North", "Tech", "Laptop", -1, 100, 0.0, 60),
            ("O11", "2024-01-01", "C1", "North", "Tech", "Laptop", 1, 0, 0.0, 60),
            ("O12", "2024-01-01", "C1", "North", "Tech", "Laptop", 1, 100, 1.5, 60),
        ]
        df, report = clean_data(raw_frame(rows))
        self.assertEqual(len(df), len(ROWS))
        self.assertEqual(report["removed"]["invalid_or_missing_date"], 1)
        self.assertEqual(report["removed"]["invalid_quantity"], 1)
        self.assertEqual(report["removed"]["invalid_unit_price"], 1)
        self.assertEqual(report["removed"]["discount_outside_0_to_1"], 1)

    def test_report_row_counts_add_up(self):
        rows = list(ROWS) + [ROWS[0]]  # one exact duplicate
        df, report = clean_data(raw_frame(rows))
        self.assertEqual(report["removed"]["duplicate_rows"], 1)
        self.assertEqual(report["rows_input"] - sum(report["removed"].values()), len(df))

    def test_missing_region_becomes_unknown_and_text_is_normalised(self):
        rows = [("O1", "2024-01-10", "C1", None, " TECH ", "Laptop", 1, 100, 0.0, 60)]
        df, report = clean_data(raw_frame(rows).replace("None", pd.NA))
        self.assertEqual(df["region"].iloc[0], "Unknown")
        self.assertEqual(df["category"].iloc[0], "Tech")
        self.assertEqual(report["filled"]["missing_region_set_to_Unknown"], 1)

    def test_missing_optional_columns_disable_profit_but_not_revenue(self):
        raw = raw_frame().drop(columns=["discount", "unit_cost"])
        df, report = clean_data(raw)
        self.assertFalse(report["has_profit_data"])
        self.assertAlmostEqual(df["revenue"].sum(), 200 + 50 + 200 + 300)  # no discount
        self.assertTrue(df["profit"].isna().all())


class GeneratorTests(unittest.TestCase):
    def test_same_seed_gives_identical_data(self):
        a = generate_sales_data(n_orders=200, n_customers=40, seed=7)
        b = generate_sales_data(n_orders=200, n_customers=40, seed=7)
        pd.testing.assert_frame_equal(a, b)

    def test_clean_generator_output_survives_cleaning_untouched(self):
        raw = generate_sales_data(n_orders=300, n_customers=50, seed=1, add_dirty_rows=False)
        df, report = clean_data(raw.astype(str))
        self.assertEqual(len(df), len(raw))
        self.assertEqual(report["removed"], {})

    def test_dirty_generator_output_is_actually_repaired(self):
        raw = generate_sales_data(n_orders=1500, n_customers=100, seed=1, add_dirty_rows=True)
        df, report = clean_data(raw.astype(str).replace({"nan": pd.NA, "None": pd.NA}))
        self.assertLess(len(df), len(raw))
        self.assertGreater(report["rows_removed_total"], 0)


if __name__ == "__main__":
    unittest.main()
