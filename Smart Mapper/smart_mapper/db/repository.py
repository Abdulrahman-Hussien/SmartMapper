from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from smart_mapper.db.staging_models import DistributorCustomerMapping, ReviewDecision, RunAuditLog


def start_run(
    session: Session,
    *,
    distributor_id: str,
    input_file_name: str,
    input_file_hash: str,
    config_version_hash: str,
) -> RunAuditLog:
    run = RunAuditLog(
        distributor_id=distributor_id,
        input_file_name=input_file_name,
        input_file_hash=input_file_hash,
        run_started_at=datetime.now(timezone.utc),
        config_version_hash=config_version_hash,
        run_status="RUNNING",
    )
    session.add(run)
    session.flush()
    return run


def finish_run(
    session: Session,
    run: RunAuditLog,
    counts: dict[str, int],
    status: str = "SUCCESS",
    error_message: str | None = None,
) -> None:
    run.run_finished_at = datetime.now(timezone.utc)
    run.rows_total = counts.get("total", 0)
    run.rows_auto_matched = counts.get("auto_matched", 0)
    run.rows_pending_review = counts.get("pending_review", 0)
    run.rows_candidate_new = counts.get("candidate_new", 0)
    run.run_status = status
    run.error_message = error_message
    session.flush()


def get_existing_mapping(session: Session, distributor_id: str, distributor_code: str) -> DistributorCustomerMapping | None:
    stmt = select(DistributorCustomerMapping).where(
        DistributorCustomerMapping.distributor_id == distributor_id,
        DistributorCustomerMapping.distributor_customer_code == distributor_code,
    )
    return session.execute(stmt).scalar_one_or_none()


def upsert_mapping(
    session: Session,
    *,
    distributor_id: str,
    distributor_customer_code: str,
    distributor_customer_name_raw: str,
    distributor_customer_address_raw: str,
    company_customer_id: str | None,
    confidence_score: float | None,
    match_method: str,
    status: str,
    candidate_alternatives: list[dict] | None,
    run_id: int,
) -> DistributorCustomerMapping:
    existing = get_existing_mapping(session, distributor_id, distributor_customer_code)

    if existing and existing.status in ("CONFIRMED", "REJECTED"):
        # A human already decided this one - never silently overwrite that.
        # Just refresh the raw text/run pointer so the row stays current.
        existing.distributor_customer_name_raw = distributor_customer_name_raw
        existing.distributor_customer_address_raw = distributor_customer_address_raw
        existing.run_id = run_id
        session.flush()
        return existing

    if existing:
        existing.distributor_customer_name_raw = distributor_customer_name_raw
        existing.distributor_customer_address_raw = distributor_customer_address_raw
        existing.company_customer_id = company_customer_id
        existing.confidence_score = confidence_score
        existing.match_method = match_method
        existing.status = status
        existing.candidate_alternatives = candidate_alternatives
        existing.run_id = run_id
        session.flush()
        return existing

    mapping = DistributorCustomerMapping(
        distributor_id=distributor_id,
        distributor_customer_code=distributor_customer_code,
        distributor_customer_name_raw=distributor_customer_name_raw,
        distributor_customer_address_raw=distributor_customer_address_raw,
        company_customer_id=company_customer_id,
        confidence_score=confidence_score,
        match_method=match_method,
        status=status,
        candidate_alternatives=candidate_alternatives,
        run_id=run_id,
    )
    session.add(mapping)
    session.flush()
    return mapping


def fetch_all_mappings(session: Session) -> list[dict]:
    """Confirmed and auto-matched mappings, used as the staging-side half of
    the exact-lookup fast path (see matching/exact_lookup.py).
    """
    stmt = select(DistributorCustomerMapping).where(DistributorCustomerMapping.company_customer_id.is_not(None))
    rows = session.execute(stmt).scalars().all()
    return [
        {
            "distributor_id": r.distributor_id,
            "distributor_code": r.distributor_customer_code,
            "company_customer_id": r.company_customer_id,
        }
        for r in rows
    ]


def apply_review_decision(
    session: Session,
    *,
    mapping_id: int,
    decision: str,
    new_company_customer_id: str | None,
    decided_by: str | None,
    source_file: str,
) -> None:
    mapping = session.get(DistributorCustomerMapping, mapping_id)
    if mapping is None:
        raise ValueError(f"No mapping row with id={mapping_id}")

    session.add(
        ReviewDecision(
            mapping_id=mapping_id,
            decision=decision,
            previous_company_customer_id=mapping.company_customer_id,
            new_company_customer_id=new_company_customer_id,
            decided_by=decided_by,
            source_file=source_file,
        )
    )

    if decision == "CONFIRM":
        mapping.status = "CONFIRMED"
        if new_company_customer_id:
            mapping.company_customer_id = new_company_customer_id
        mapping.match_method = "FUZZY_REVIEW_CONFIRMED"
    elif decision == "REJECT":
        mapping.status = "REJECTED"
    elif decision == "REASSIGN":
        mapping.status = "CONFIRMED"
        mapping.company_customer_id = new_company_customer_id
        mapping.match_method = "MANUAL_NEW_CUSTOMER_LINK"
    else:
        raise ValueError(f"Unknown decision '{decision}', expected CONFIRM/REJECT/REASSIGN")

    mapping.reviewed_by = decided_by
    mapping.reviewed_at = datetime.now(timezone.utc)
    session.flush()
