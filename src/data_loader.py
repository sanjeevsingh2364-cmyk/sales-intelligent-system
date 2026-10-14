"""
Data ingestion: read a CSV / Excel file and validate its structure.

Everything is read as TEXT (dtype=str) on purpose. Type conversion is the job of
data_cleaning.py, where invalid values are counted and reported instead of
silently breaking the load.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import BinaryIO, Union

import pandas as pd

import config

Source = Union[str, Path, BinaryIO]


class DataValidationError(Exception):
    """Raised when the input file is missing, unreadable or has the wrong columns."""


def normalise_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """'Order Date ' -> 'order_date' (lowercase, trimmed, spaces/hyphens to underscores)."""
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)     # BOM left by some Excel exports
        .str.strip()
        .str.lower()
        .str.replace(r"[\s\-]+", "_", regex=True)
    )
    return df


def validate_columns(df: pd.DataFrame) -> None:
    """Raise a friendly error if any required column is missing."""
    missing = [c for c in config.REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Required columns are: {', '.join(config.REQUIRED_COLUMNS)}. "
            f"Columns found in your file: {', '.join(map(str, df.columns))}."
        )


def load_data(source: Source, filename: str | None = None) -> pd.DataFrame:
    """Load a .csv or .xlsx file (path or file-like object) as a raw text DataFrame."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise DataValidationError(f"File not found: {path}")
        name, handle = path.name, path
    else:
        name = filename or getattr(source, "name", None)
        handle = source
    if not name:
        raise DataValidationError("Could not determine the file name / type.")

    suffix = Path(name).suffix.lower()
    try:
        if suffix == ".csv":
            raw = pd.read_csv(handle, dtype=str)
        elif suffix == ".xlsx":
            raw = pd.read_excel(handle, dtype=str, engine="openpyxl")
        else:
            raise DataValidationError(
                f"Unsupported file type '{suffix}'. Please upload a .csv or .xlsx file."
            )
    except DataValidationError:
        raise
    except pd.errors.EmptyDataError as exc:
        raise DataValidationError(f"'{name}' is empty.") from exc
    except (ValueError, UnicodeDecodeError, OSError, zipfile.BadZipFile) as exc:
        raise DataValidationError(f"Could not read '{name}': {exc}") from exc

    if raw.empty:
        raise DataValidationError(f"'{name}' has headers but no data rows.")

    raw = normalise_column_names(raw)
    validate_columns(raw)
    return raw
