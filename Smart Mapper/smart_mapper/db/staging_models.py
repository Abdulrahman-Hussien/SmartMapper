from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# BigInteger as a SQLite primary key doesn't get autoincrement rowid
# behavior the way plain INTEGER PRIMARY KEY does - falls back to Integer
# there (SQLite is dynamically typed anyway), stays BigInteger on the real
# MySQL/Postgres target.
_PkType = BigInteger().with_variant(Integer(), "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunAuditLog(Base):
    __tablename__ = "run_audit_log"

    id = Column(_PkType, primary_key=True, autoincrement=True)
    distributor_id = Column(String(50), nullable=False)
    input_file_name = Column(String(255), nullable=False)
    input_file_hash = Column(String(64), nullable=False)
    run_started_at = Column(DateTime, nullable=False)
    run_finished_at = Column(DateTime, nullable=True)
    rows_total = Column(Integer, default=0)
    rows_auto_matched = Column(Integer, default=0)
    rows_pending_review = Column(Integer, default=0)
    rows_candidate_new = Column(Integer, default=0)
    config_version_hash = Column(String(64), nullable=True)
    run_status = Column(String(20), default="RUNNING")
    error_message = Column(Text, nullable=True)


class DistributorCustomerMapping(Base):
    __tablename__ = "distributor_customer_mapping"
    __table_args__ = (UniqueConstraint("distributor_id", "distributor_customer_code", name="uq_distributor_code"),)

    id = Column(_PkType, primary_key=True, autoincrement=True)
    distributor_id = Column(String(50), nullable=False)
    distributor_customer_code = Column(String(100), nullable=False)
    distributor_customer_name_raw = Column(Text)
    distributor_customer_address_raw = Column(Text)
    company_customer_id = Column(String(100), nullable=True)
    confidence_score = Column(Numeric(5, 4), nullable=True)
    match_method = Column(String(30), nullable=True)
    status = Column(String(20), nullable=False, default="PENDING_REVIEW")
    candidate_alternatives = Column(JSON, nullable=True)
    run_id = Column(BigInteger, ForeignKey("run_audit_log.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id = Column(_PkType, primary_key=True, autoincrement=True)
    mapping_id = Column(BigInteger, ForeignKey("distributor_customer_mapping.id"), nullable=False)
    decision = Column(String(20), nullable=False)
    previous_company_customer_id = Column(String(100), nullable=True)
    new_company_customer_id = Column(String(100), nullable=True)
    decided_by = Column(String(100), nullable=True)
    decided_at = Column(DateTime, default=_utcnow)
    source_file = Column(String(255), nullable=True)


def create_staging_tables(engine: Engine) -> None:
    """Creates ONLY the three tables above. Must be run deliberately, once,
    by whoever holds the staging DB credential - never called implicitly
    from a normal `smart-mapper run`.
    """
    Base.metadata.create_all(engine)
