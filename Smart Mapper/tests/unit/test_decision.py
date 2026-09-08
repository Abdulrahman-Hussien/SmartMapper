from smart_mapper.config_loader import ThresholdSpec
from smart_mapper.matching.decision import MatchStatus, decide
from smart_mapper.matching.scoring import CandidateScore


def _score(customer_id: str, composite: float) -> CandidateScore:
    return CandidateScore(
        customer_id=customer_id, name_score=composite, address_score=composite, city_bonus=1.0, phone_score=None, composite=composite
    )


def test_auto_matched_above_threshold():
    thresholds = ThresholdSpec(auto_accept_threshold=0.9, review_lower_threshold=0.7)
    decision = decide([_score("C1", 0.95)], thresholds)
    assert decision.status == MatchStatus.AUTO_MATCHED
    assert decision.matched_customer_id == "C1"


def test_pending_review_between_thresholds():
    thresholds = ThresholdSpec(auto_accept_threshold=0.9, review_lower_threshold=0.7)
    decision = decide([_score("C1", 0.8)], thresholds)
    assert decision.status == MatchStatus.PENDING_REVIEW


def test_new_customer_below_review_threshold():
    thresholds = ThresholdSpec(auto_accept_threshold=0.9, review_lower_threshold=0.7)
    decision = decide([_score("C1", 0.3)], thresholds)
    assert decision.status == MatchStatus.CANDIDATE_NEW_CUSTOMER
    assert decision.matched_customer_id is None


def test_no_candidates_is_new_customer():
    thresholds = ThresholdSpec(auto_accept_threshold=0.9, review_lower_threshold=0.7)
    decision = decide([], thresholds)
    assert decision.status == MatchStatus.CANDIDATE_NEW_CUSTOMER
