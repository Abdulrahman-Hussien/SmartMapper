from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process

from smart_mapper.normalization.pipeline import ProcessedRecord


@dataclass
class MasterCustomer:
    customer_id: str
    processed: ProcessedRecord


class CandidateIndex:
    """Blocking index over the customer master so an incoming row is only
    compared against a plausible shortlist, not every customer in the DB.
    """

    def __init__(self, customers: list[MasterCustomer]):
        self.customers = customers
        self.by_city: dict[str, list[MasterCustomer]] = {}
        self.by_first_token: dict[str, list[MasterCustomer]] = {}
        for c in customers:
            if c.processed.city_token:
                self.by_city.setdefault(c.processed.city_token, []).append(c)
            if c.processed.name_tokens:
                self.by_first_token.setdefault(c.processed.name_tokens[0], []).append(c)

    def candidates_for(self, record: ProcessedRecord, limit: int) -> list[MasterCustomer]:
        shortlist: list[MasterCustomer] = []
        seen_ids: set[str] = set()

        def add_all(items: list[MasterCustomer]) -> None:
            for item in items:
                if item.customer_id not in seen_ids:
                    shortlist.append(item)
                    seen_ids.add(item.customer_id)

        if record.city_token and record.city_token in self.by_city:
            add_all(self.by_city[record.city_token])

        if record.name_tokens and record.name_tokens[0] in self.by_first_token:
            add_all(self.by_first_token[record.name_tokens[0]])

        if not shortlist:
            add_all(self.customers)

        if len(shortlist) > limit:
            choices = {c.customer_id: c.processed.name_text for c in shortlist}
            pre_scored = process.extract(record.name_text, choices, scorer=fuzz.WRatio, limit=limit)
            keep_ids = {match[2] for match in pre_scored}
            shortlist = [c for c in shortlist if c.customer_id in keep_ids]

        return shortlist
