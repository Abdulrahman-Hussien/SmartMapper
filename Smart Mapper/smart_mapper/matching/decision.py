from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from smart_mapper.config_loader import ThresholdSpec
from smart_mapper.matching.scoring import CandidateScore


class MatchStatus(str, Enum):
    AUTO_MATCHED = "AUTO_MATCHED"
    PENDING_REVIEW = "PENDING_REVIEW"
    CANDIDATE_NEW_CUSTOMER = "CANDIDATE_NEW_CUSTOMER"


@dataclass
class Decision:
    status: MatchStatus
    matched_customer_id: str | None
    confidence: float | None
    alternatives: list[CandidateScore]


def decide(
    scored_candidates: list[CandidateScore],
    thresholds: ThresholdSpec,
    top_n_alternatives: int = 3,
) -> Decision:
    if not scored_candidates:
        return Decision(MatchStatus.CANDIDATE_NEW_CUSTOMER, None, None, [])

    top = scored_candidates[0]

    if top.composite >= thresholds.auto_accept_threshold:
        return Decision(MatchStatus.AUTO_MATCHED, top.customer_id, top.composite, scored_candidates[1:top_n_alternatives])
    if top.composite >= thresholds.review_lower_threshold:
        return Decision(MatchStatus.PENDING_REVIEW, top.customer_id, top.composite, scored_candidates[1:top_n_alternatives])
    return Decision(MatchStatus.CANDIDATE_NEW_CUSTOMER, None, top.composite, scored_candidates[:top_n_alternatives])
