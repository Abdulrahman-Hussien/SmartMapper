from __future__ import annotations

from dataclasses import dataclass

from smart_mapper.normalization.address_parser import extract_city_token
from smart_mapper.normalization.arabic_text import normalize
from smart_mapper.normalization.synonyms import apply_synonyms


@dataclass
class ProcessedRecord:
    raw_name: str
    raw_address: str
    name_tokens: list[str]
    address_tokens: list[str]
    name_text: str
    address_text: str
    city_token: str | None
    phone: str | None = None


def process_record(
    name: str | None,
    address: str | None,
    name_synonym_lookup: dict[str, str],
    address_synonym_lookup: dict[str, str],
    city_lookup: dict[str, str],
    phone: str | None = None,
) -> ProcessedRecord:
    """Runs the full normalize -> synonym-substitute -> city-extract pipeline
    on a raw name/address pair. Used identically for incoming distributor rows
    and for customer master rows, so both sides are comparable.
    """
    name_norm = normalize(name)
    address_norm = normalize(address)

    name_tokens = apply_synonyms(name_norm.tokens, name_synonym_lookup)
    address_tokens = apply_synonyms(address_norm.tokens, address_synonym_lookup)

    city_token = extract_city_token(address_tokens, city_lookup)

    return ProcessedRecord(
        raw_name=name or "",
        raw_address=address or "",
        name_tokens=name_tokens,
        address_tokens=address_tokens,
        name_text=" ".join(name_tokens),
        address_text=" ".join(address_tokens),
        city_token=city_token,
        phone=phone.strip() if phone else None,
    )
