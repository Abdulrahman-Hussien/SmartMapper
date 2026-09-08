from __future__ import annotations

from sqlalchemy import MetaData, Table, select
from sqlalchemy.engine import Engine

from smart_mapper.config_loader import SettingsConfig

# Deliberately reflection-based, not hand-written ORM models: these tables
# already exist and are owned by the core system. Only SELECT is ever issued
# against them here - there is no code path in this module capable of
# INSERT/UPDATE/DELETE, by construction, not just by convention.


def reflect_table(engine: Engine, table_name: str) -> Table:
    metadata = MetaData()
    return Table(table_name, metadata, autoload_with=engine)


def fetch_customer_master(engine: Engine, settings: SettingsConfig) -> list[dict]:
    cfg = settings.core_db.customer_master
    table = reflect_table(engine, cfg.table)
    cols = cfg.columns

    select_cols = [
        table.c[cols.id].label("customer_id"),
        table.c[cols.name].label("name"),
        table.c[cols.address].label("address"),
    ]
    if cols.city:
        select_cols.append(table.c[cols.city].label("city"))
    if cols.phone:
        select_cols.append(table.c[cols.phone].label("phone"))

    with engine.connect() as conn:
        result = conn.execute(select(*select_cols))
        return [dict(row._mapping) for row in result]


def fetch_historical_mappings(engine: Engine, settings: SettingsConfig) -> list[dict]:
    cfg = settings.core_db.historical_mapping
    table = reflect_table(engine, cfg.table)
    cols = cfg.columns

    select_cols = [
        table.c[cols.distributor_id].label("distributor_id"),
        table.c[cols.distributor_code].label("distributor_code"),
        table.c[cols.company_customer_id].label("company_customer_id"),
    ]
    if cols.distributor_name_raw:
        select_cols.append(table.c[cols.distributor_name_raw].label("distributor_name_raw"))
    if cols.distributor_address_raw:
        select_cols.append(table.c[cols.distributor_address_raw].label("distributor_address_raw"))

    with engine.connect() as conn:
        result = conn.execute(select(*select_cols))
        return [dict(row._mapping) for row in result]
