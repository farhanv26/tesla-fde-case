"""Workbook loading and inspection helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from utils import ensure_directory, get_project_root, to_snake_case


def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Return a dataframe copy with snake_case column names."""
    standardized = df.copy()
    standardized.columns = [to_snake_case(str(column)) for column in standardized.columns]
    return standardized


def _resolve_workbook_path(expected_filename: str, fallback_pattern: str, data_dir: Path) -> Path:
    """Resolve workbook path by exact name first, then fallback glob pattern."""
    expected_path = data_dir / expected_filename
    if expected_path.exists():
        return expected_path

    matches = sorted(data_dir.glob(fallback_pattern))
    if not matches:
        raise FileNotFoundError(
            f"Could not find workbook '{expected_filename}' or any file matching '{fallback_pattern}' in {data_dir}."
        )
    return matches[0]


def load_all_workbook_sheets(workbook_path: Path) -> dict[str, pd.DataFrame]:
    """Load all sheets from a workbook and standardize column names."""
    sheets = pd.read_excel(workbook_path, sheet_name=None)
    return {sheet_name: standardize_column_names(df) for sheet_name, df in sheets.items()}


def sheet_missing_value_summary(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    """Build a per-column missing value summary for one sheet."""
    missing_count = df.isna().sum()
    missing_pct = (missing_count / len(df) * 100).round(2) if len(df) else 0.0
    return pd.DataFrame(
        {
            "sheet_name": sheet_name,
            "column_name": df.columns,
            "missing_count": missing_count.values,
            "missing_percent": missing_pct.values if hasattr(missing_pct, "values") else missing_pct,
        }
    )


def inspect_workbook(
    workbook_path: Path,
    output_dir: Path,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    """
    Inspect all sheets in a workbook.

    Returns loaded sheets plus two summary dataframes:
    - workbook-level sheet metadata summary
    - missing values summary by sheet and column
    """
    workbook_name = workbook_path.stem
    print(f"\n{'=' * 80}")
    print(f"Workbook: {workbook_name}")
    print(f"Path: {workbook_path}")
    print(f"{'=' * 80}")

    sheets = load_all_workbook_sheets(workbook_path)
    workbook_summary_rows: list[dict[str, Any]] = []
    missing_summaries: list[pd.DataFrame] = []

    for sheet_name, df in sheets.items():
        print(f"\nSheet: {sheet_name}")
        print(f"Rows: {len(df):,} | Columns: {len(df.columns)}")
        print("Columns:", list(df.columns))
        print("Dtypes:")
        print(df.dtypes)
        print("First 5 rows:")
        print(df.head(5))

        workbook_summary_rows.append(
            {
                "workbook": workbook_name,
                "sheet_name": sheet_name,
                "row_count": len(df),
                "column_count": len(df.columns),
                "column_names": " | ".join(df.columns.astype(str)),
                "dtypes": " | ".join([f"{col}:{dtype}" for col, dtype in df.dtypes.items()]),
            }
        )
        missing_summaries.append(sheet_missing_value_summary(df=df, sheet_name=sheet_name))

    workbook_summary_df = pd.DataFrame(workbook_summary_rows)
    missing_summary_df = pd.concat(missing_summaries, ignore_index=True) if missing_summaries else pd.DataFrame()

    ensure_directory(output_dir)
    workbook_summary_path = output_dir / f"{workbook_name}_sheet_summary.csv"
    missing_summary_path = output_dir / f"{workbook_name}_missing_summary.csv"
    workbook_summary_df.to_csv(workbook_summary_path, index=False)
    missing_summary_df.to_csv(missing_summary_path, index=False)
    print(f"\nSaved workbook summary: {workbook_summary_path}")
    print(f"Saved missing summary: {missing_summary_path}")

    return sheets, workbook_summary_df, missing_summary_df


def inspect_all_target_workbooks() -> dict[str, dict[str, pd.DataFrame]]:
    """Load and inspect all target Tesla case-study workbooks."""
    project_root = get_project_root()
    data_dir = project_root / "data"
    output_dir = project_root / "outputs" / "cleaned"

    target_workbooks = [
        (
            "Tesla_FDE_Challenge_Data.xlsx",
            "Tesla_FDE_Challenge_Data*.xlsx",
        ),
        (
            "TESLA_NewProject_Estimate.xlsx",
            "TESLA_NewProject_Estimate*.xlsx",
        ),
    ]

    loaded_workbooks: dict[str, dict[str, pd.DataFrame]] = {}
    for expected_name, fallback_pattern in target_workbooks:
        workbook_path = _resolve_workbook_path(
            expected_filename=expected_name,
            fallback_pattern=fallback_pattern,
            data_dir=data_dir,
        )
        sheets, _, _ = inspect_workbook(workbook_path=workbook_path, output_dir=output_dir)
        loaded_workbooks[workbook_path.stem] = sheets

    return loaded_workbooks
