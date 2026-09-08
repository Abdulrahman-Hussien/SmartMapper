from smart_mapper.normalization.arabic_text import normalize


def test_alef_variants_unified():
    assert normalize("أحمد").normalized == normalize("احمد").normalized
    assert normalize("إحمد").normalized == normalize("احمد").normalized
    assert normalize("آحمد").normalized == normalize("احمد").normalized


def test_ya_and_ta_marbuta_unified():
    assert normalize("صيدلية").normalized == normalize("صيدليه").normalized
    assert normalize("مصطفى").normalized == normalize("مصطفي").normalized


def test_diacritics_and_tatweel_stripped():
    assert normalize("مُحَمَّد").normalized == normalize("محمد").normalized
    assert normalize("محمـد").normalized == normalize("محمد").normalized


def test_arabic_indic_digits_normalized():
    assert normalize("شارع ١٠").normalized == normalize("شارع 10").normalized


def test_empty_and_none_input():
    assert normalize(None).normalized == ""
    assert normalize("   ").normalized == ""


def test_tokens_populated():
    result = normalize("صيدلية النور")
    assert len(result.tokens) == 2
