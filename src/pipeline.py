"""
Pipeline = load -> validate -> clean. Used by the dashboard and by the CLI.

CLI (from project root):
    python -m src.pipeline                      # processes the synthetic sample
    python -m src.pipeline --input my_file.csv  # processes your own file
"""

from __future__ import annotations

import argparse
import json

import config
from src.data_cleaning import clean_data
from src.data_loader import DataValidationError, Source, load_data


def load_and_clean(source: Source, filename: str | None = None):
    """Load, validate and clean a file. Returns (clean_df, report)."""
    raw = load_data(source, filename=filename)
    return clean_data(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean a sales file and save the result.")
    parser.add_argument("--input", default=str(config.SAMPLE_DATA_PATH))
    args = parser.parse_args()

    try:
        clean_df, report = load_and_clean(args.input)
    except DataValidationError as exc:
        raise SystemExit(f"Data error: {exc}")

    config.DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(config.PROCESSED_DATA_PATH, index=False)
    config.CLEANING_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nSaved: {config.PROCESSED_DATA_PATH}")


if __name__ == "__main__":
    main()
