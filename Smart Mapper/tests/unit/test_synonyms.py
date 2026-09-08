import pytest

from smart_mapper.config_loader import SynonymsFile
from smart_mapper.normalization.arabic_text import normalize
from smart_mapper.normalization.synonyms import apply_synonyms, build_normalized_lookup


def test_variant_maps_to_canonical():
    raw = {"ص": "صيدلية", "صيدليه": "صيدلية"}
    lookup = build_normalized_lookup(raw)

    tokens = normalize("ص النور").tokens
    result = apply_synonyms(tokens, lookup)

    assert result[0] == normalize("صيدلية").normalized


def test_conflicting_synonyms_raise():
    data = {
        "groups": [
            {"canonical": "صيدلية", "variants": ["ص"]},
            {"canonical": "شركة", "variants": ["ص"]},
        ]
    }
    with pytest.raises(ValueError):
        SynonymsFile(**data).to_lookup()


def test_non_matching_token_is_left_unchanged():
    lookup = build_normalized_lookup({"ص": "صيدلية"})
    tokens = normalize("مستشفى الشفاء").tokens
    result = apply_synonyms(tokens, lookup)
    assert result == tokens
