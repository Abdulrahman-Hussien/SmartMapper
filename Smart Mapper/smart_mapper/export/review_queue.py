from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_review_queue(rows: list[dict], output_path: str | Path) -> None:
    """rows: dicts with distributor_code, distributor_name_raw, distributor_address_raw,
    candidate_customer_id, candidate_name, candidate_address, confidence, and
    alternative_N_id/name/score columns for the runner-up candidates.

    Adds blank columns for a human reviewer to fill in and hand back to
    `smart-mapper ingest-review`.
    """
    df = pd.DataFrame(rows)
    df["decision"] = ""  # CONFIRM / REJECT / REASSIGN
    df["confirmed_company_customer_id"] = ""
    df["reviewed_by"] = ""
    df["reviewer_notes"] = ""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)
