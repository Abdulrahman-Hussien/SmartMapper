from __future__ import annotations

import pandas as pd
from loguru import logger

from smart_mapper.config_loader import DistributorAdapterConfig
from smart_mapper.ingestion.canonical_schema import RawCustomerRow
from smart_mapper.ingestion.file_readers import read_table


def load_distributor_rows(config: DistributorAdapterConfig, file_path: str) -> list[RawCustomerRow]:
    df = read_table(file_path, config.file_type, config.sheet_name, config.header_row_index, config.encoding)

    cols = config.columns
    required = [cols.customer_code, cols.customer_name, cols.customer_address]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Distributor '{config.distributor_id}' file is missing expected column(s): {missing}. "
            f"Found columns: {list(df.columns)}"
        )

    rows: list[RawCustomerRow] = []
    skipped = 0
    for _, row in df.iterrows():
        code = _clean(row.get(cols.customer_code))
        if not code and config.skip_rows_where_code_blank:
            skipped += 1
            continue

        rows.append(
            RawCustomerRow(
                code=code or "",
                name=_clean(row.get(cols.customer_name)) or "",
                address=_clean(row.get(cols.customer_address)) or "",
                city=_clean(row.get(cols.city)) if cols.city else None,
                phone=_clean(row.get(cols.phone)) if cols.phone else None,
            )
        )

    if skipped:
        logger.warning(f"Skipped {skipped} row(s) with blank customer code in {file_path}")

    return rows


def _clean(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None
