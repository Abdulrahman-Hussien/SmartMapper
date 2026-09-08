from smart_mapper.config_loader import MatchingWeights
from smart_mapper.matching.candidate_generation import MasterCustomer
from smart_mapper.matching.scoring import score_candidate
from smart_mapper.normalization.pipeline import process_record


def _record(name, address):
    return process_record(name, address, {}, {}, {})


def test_identical_records_score_high():
    weights = MatchingWeights()
    record = _record("صيدلية النور", "شارع الجمهورية القاهرة")
    candidate = MasterCustomer(customer_id="C1", processed=_record("صيدلية النور", "شارع الجمهورية القاهرة"))

    score = score_candidate(record, candidate, weights)

    assert score.composite > 0.95


def test_different_records_score_low():
    weights = MatchingWeights()
    record = _record("صيدلية النور", "شارع الجمهورية القاهرة")
    candidate = MasterCustomer(customer_id="C2", processed=_record("مستشفى الشفاء", "شارع فيصل الجيزة"))

    score = score_candidate(record, candidate, weights)

    assert score.composite < 0.5


def test_slightly_different_spelling_still_scores_high():
    # صيدليه (ta-marbuta as ه) vs صيدلية (ة) - should be unified by normalization
    weights = MatchingWeights()
    record = _record("صيدليه النور", "شارع الجمهوريه")
    candidate = MasterCustomer(customer_id="C3", processed=_record("صيدلية النور", "شارع الجمهورية"))

    score = score_candidate(record, candidate, weights)

    assert score.composite > 0.95
