from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from smart_mapper.config_loader import MatchingWeights
from smart_mapper.matching.candidate_generation import MasterCustomer
from smart_mapper.normalization.pipeline import ProcessedRecord


@dataclass
class CandidateScore:
    customer_id: str
    name_score: float
    address_score: float
    city_bonus: float | None
    phone_score: float | None
    composite: float


def score_candidate(record: ProcessedRecord, candidate: MasterCustomer, weights: MatchingWeights) -> CandidateScore:
    # token_set_ratio for names: word order / extra descriptive tokens
    # ("صيدلية النور فرع مدينة نصر") shouldn't tank the score.
    name_score = fuzz.token_set_ratio(record.name_text, candidate.processed.name_text) / 100.0
    # token_sort_ratio for addresses: order differences are common, but a
    # *set* ratio would over-forgive missing components, so sort (not set).
    address_score = fuzz.token_sort_ratio(record.address_text, candidate.processed.address_text) / 100.0

    # City/phone are supporting signals, not always available. When a signal
    # is missing on either side it's excluded from the average entirely
    # (like phone below) rather than counted as a neutral penalty - an
    # address with no recognizable city token must not be structurally
    # incapable of ever scoring as a strong match.
    city_bonus = None
    if record.city_token and candidate.processed.city_token:
        city_bonus = 1.0 if record.city_token == candidate.processed.city_token else 0.0

    phone_score = None
    if record.phone and candidate.processed.phone:
        phone_score = 1.0 if record.phone == candidate.processed.phone else 0.0

    total_weight = weights.name + weights.address
    weighted_sum = weights.name * name_score + weights.address * address_score
    if city_bonus is not None:
        total_weight += weights.city
        weighted_sum += weights.city * city_bonus
    if phone_score is not None:
        total_weight += weights.phone
        weighted_sum += weights.phone * phone_score

    composite = weighted_sum / total_weight if total_weight else 0.0

    return CandidateScore(
        customer_id=candidate.customer_id,
        name_score=name_score,
        address_score=address_score,
        city_bonus=city_bonus,
        phone_score=phone_score,
        composite=composite,
    )


def score_candidates(
    record: ProcessedRecord, candidates: list[MasterCustomer], weights: MatchingWeights
) -> list[CandidateScore]:
    scores = [score_candidate(record, c, weights) for c in candidates]
    scores.sort(key=lambda s: s.composite, reverse=True)
    return scores
