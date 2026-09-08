"""Phase 0 discovery tool - read-only. Dumps table/column names visible to
the CORE_DB_URL credential so config/settings.yaml can be filled in with
real table/column names. Issues no writes; uses SQLAlchemy's inspector only.

Usage:
    python scripts/inspect_schema.py
    python scripts/inspect_schema.py --table customers
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv
from sqlalchemy import inspect

from smart_mapper.db.engine import get_core_engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", help="If given, only show columns for this table")
    args = parser.parse_args()

    load_dotenv()
    engine = get_core_engine()
    inspector = inspect(engine)

    if args.table:
        _print_table(inspector, args.table)
        return

    print("Tables visible to this (read-only) credential:")
    for table_name in inspector.get_table_names():
        print(f"  - {table_name}")
    print("\nRun again with --table <name> to see its columns.")


def _print_table(inspector, table_name: str) -> None:
    print(f"Columns in '{table_name}':")
    for col in inspector.get_columns(table_name):
        print(f"  - {col['name']}  ({col['type']})")

    pk = inspector.get_pk_constraint(table_name)
    if pk.get("constrained_columns"):
        print(f"Primary key: {pk['constrained_columns']}")


if __name__ == "__main__":
    main()
