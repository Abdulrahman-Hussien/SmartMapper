from __future__ import annotations

from smart_mapper.normalization.arabic_text import normalize


def build_normalized_lookup(raw_lookup: dict[str, str]) -> dict[str, str]:
    """The YAML synonym files are authored in plain Arabic text; normalize
    both sides the same way tokens are normalized so lookups actually hit
    regardless of diacritics/letter-variant differences in how they were typed.
    """
    result: dict[str, str] = {}
    for variant, canonical in raw_lookup.items():
        norm_variant = normalize(variant).normalized
        norm_canonical = normalize(canonical).normalized
        if norm_variant:
            result[norm_variant] = norm_canonical
    return result


def apply_synonyms(tokens: list[str], lookup: dict[str, str]) -> list[str]:
    """Replace each (already-normalized) token with its canonical form if defined."""
    return [lookup.get(token, token) for token in tokens]


def canonical_text(tokens: list[str], lookup: dict[str, str]) -> str:
    return " ".join(apply_synonyms(tokens, lookup))
