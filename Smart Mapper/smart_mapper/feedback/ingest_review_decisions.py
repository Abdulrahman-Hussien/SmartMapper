from __future__ import annotations

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from smart_mapper.db.repository import apply_review_decision, get_existing_mapping

_VALID_DECISIONS = {"CONFIRM", "REJECT", "REASSIGN"}


def ingest_review_file(session: Session, file_path: str, distributor_id: str) -> dict[str, int]:
    df = pd.read_excel(file_path, dtype=str)
    required_cols = {"distributor_code", "decision"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Review file is missing required column(s): {missing}")

    counts = {"confirmed": 0, "rejected": 0, "reassigned": 0, "skipped": 0}

    for _, row in df.iterrows():
        decision = (row.get("decision") or "").strip().upper()
        if decision not in _VALID_DECISIONS:
            counts["skipped"] += 1
            continue

        distributor_code = str(row["distributor_code"]).strip()
        mapping = get_existing_mapping(session, distributor_id, distributor_code)
        if mapping is None:
            logger.warning(f"No staging mapping found for distributor_code={distributor_code}, skipping")
            counts["skipped"] += 1
            continue

        confirmed_id = row.get("confirmed_company_customer_id")
        new_id = str(confirmed_id).strip() if confirmed_id and str(confirmed_id).strip() else mapping.company_customer_id

        apply_review_decision(
            session,
            mapping_id=mapping.id,
            decision=decision,
            new_company_customer_id=new_id,
            decided_by=row.get("reviewed_by"),
            source_file=file_path,
        )
        counts[{"CONFIRM": "confirmed", "REJECT": "rejected", "REASSIGN": "reassigned"}[decision]] += 1

    session.commit()
    return counts
