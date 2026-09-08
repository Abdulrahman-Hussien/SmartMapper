from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def get_core_engine() -> Engine:
    """Connection used ONLY for SELECT queries against the existing company
    database (customer master, historical mapping table). The credential in
    CORE_DB_URL should be a DB-enforced read-only account - see .env.example.
    """
    url = os.environ["CORE_DB_URL"]
    return create_engine(url, pool_pre_ping=True)


def get_staging_engine() -> Engine:
    """Connection used for the mapper's own staging tables. Defaults to
    CORE_DB_URL for local development only; production should use a
    dedicated STAGING_DB_URL credential scoped to just these tables/schema.
    """
    url = os.environ.get("STAGING_DB_URL") or os.environ["CORE_DB_URL"]
    return create_engine(url, pool_pre_ping=True)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
