from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_run_summary(mapped_rows: list[dict], counts: dict[str, int], output_path: str | Path) -> None:
    summary_df = pd.DataFrame([counts])
    mapped_df = pd.DataFrame(mapped_rows)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path) as writer:
        summary_df.to_excel(writer, sheet_name="summary", index=False)
        mapped_df.to_excel(writer, sheet_name="mapped_report", index=False)
