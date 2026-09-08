from __future__ import annotations

from smart_mapper.normalization.arabic_text import normalize


def build_city_lookup(known_cities: dict[str, list[str]]) -> dict[str, str]:
    """known_cities maps a canonical city name to a list of spelling variants
    (from config/settings.yaml). Returns normalized-variant -> normalized-canonical.
    """
    lookup: dict[str, str] = {}
    for canonical, variants in known_cities.items():
        canonical_norm = normalize(canonical).normalized
        lookup[canonical_norm] = canonical_norm
        for variant in variants:
            variant_norm = normalize(variant).normalized
            if variant_norm:
                lookup[variant_norm] = canonical_norm
    return lookup


def extract_city_token(tokens: list[str], city_lookup: dict[str, str]) -> str | None:
    """Looks for a known city name among single tokens, then two-word phrases
    (some city names are two words, e.g. مدينة نصر).
    """
    for token in tokens:
        if token in city_lookup:
            return city_lookup[token]
    for i in range(len(tokens) - 1):
        bigram = f"{tokens[i]} {tokens[i + 1]}"
        if bigram in city_lookup:
            return city_lookup[bigram]
    return None
