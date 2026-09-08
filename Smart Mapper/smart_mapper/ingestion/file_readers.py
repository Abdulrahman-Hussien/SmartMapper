from __future__ import annotations

import pandas as pd


def read_table(
    path: str,
    file_type: str,
    sheet_name: str | None,
    header_row_index: int,
    encoding: str,
) -> pd.DataFrame:
    if file_type == "xlsx":
        return pd.read_excel(path, sheet_name=sheet_name or 0, header=header_row_index, dtype=str)
    if file_type == "csv":
        try:
            return pd.read_csv(path, header=header_row_index, encoding=encoding, dtype=str)
        except UnicodeDecodeError:
            # Legacy Arabic Windows exports are sometimes cp1256 instead of utf-8.
            return pd.read_csv(path, header=header_row_index, encoding="cp1256", dtype=str)
    raise ValueError(f"Unsupported file_type: {file_type!r} (expected 'xlsx' or 'csv')")
