from __future__ import annotations


def build_history_index(mapping_rows: list[dict]) -> dict[tuple[str, str], str]:
    """mapping_rows: dicts with distributor_id, distributor_code, company_customer_id.

    Pass historical-mapping rows first and staging-table rows second (or vice
    versa per caller's intent) - later rows in the list win on key collision,
    so callers control precedence explicitly rather than it being implicit here.
    """
    index: dict[tuple[str, str], str] = {}
    for row in mapping_rows:
        if row.get("company_customer_id"):
            index[(row["distributor_id"], row["distributor_code"])] = row["company_customer_id"]
    return index


def lookup_exact(distributor_id: str, distributor_code: str, index: dict[tuple[str, str], str]) -> str | None:
    return index.get((distributor_id, distributor_code))
