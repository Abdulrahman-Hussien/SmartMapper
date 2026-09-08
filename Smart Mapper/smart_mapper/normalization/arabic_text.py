from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from pyarabic import araby

_ALEF_VARIANTS = "أإآٱ"
_ALEF_TRANSLATION = str.maketrans({c: "ا" for c in _ALEF_VARIANTS})

_YA_TRANSLATION = str.maketrans({"ى": "ي"})
_TA_MARBUTA_TRANSLATION = str.maketrans({"ة": "ه"})
_HAMZA_CARRIER_TRANSLATION = str.maketrans({"ؤ": "ء", "ئ": "ء"})

_ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_DIGIT_TRANSLATION = str.maketrans({d: str(i) for i, d in enumerate(_ARABIC_INDIC_DIGITS)})

_PUNCTUATION_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class NormalizedText:
    raw: str
    normalized: str
    tokens: list[str] = field(default_factory=list)


def normalize(text: str | None, unify_hamza: bool = False) -> NormalizedText:
    """Deterministic Arabic text normalization for matching purposes only -
    never use `.normalized`/`.tokens` for display, always keep `.raw` for that.
    """
    raw = text or ""
    if not raw.strip():
        return NormalizedText(raw=raw, normalized="", tokens=[])

    t = unicodedata.normalize("NFKC", raw)
    t = araby.strip_tashkeel(t)
    t = araby.strip_tatweel(t)
    t = t.translate(_ALEF_TRANSLATION)
    t = t.translate(_YA_TRANSLATION)
    t = t.translate(_TA_MARBUTA_TRANSLATION)
    if unify_hamza:
        t = t.translate(_HAMZA_CARRIER_TRANSLATION)
    t = t.translate(_DIGIT_TRANSLATION)
    t = _PUNCTUATION_RE.sub(" ", t)
    t = _WHITESPACE_RE.sub(" ", t).strip()
    t = t.lower()

    tokens = t.split(" ") if t else []
    return NormalizedText(raw=raw, normalized=t, tokens=tokens)
