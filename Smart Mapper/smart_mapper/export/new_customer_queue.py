from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_new_customer_queue(rows: list[dict], output_path: str | Path) -> None:
    """rows: dicts with distributor_code, distributor_name_raw, distributor_address_raw,
    and best_partial_match_id/name/score (in case the "new" flag is actually a
    very messy existing customer, so reviewers can double check).

    The mapper never auto-creates customers in the core database - this file
    is the hand-off point for a human to verify and create the record.
    """
    df = pd.DataFrame(rows)
    df["onboarding_decision"] = ""  # CREATE / MATCH_EXISTING / IGNORE
    df["linked_company_customer_id"] = ""
    df["reviewer_notes"] = ""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)
