from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from smart_mapper.config_loader import MatchingWeights
from smart_mapper.matching.candidate_generation import CandidateIndex, MasterCustomer
from smart_mapper.matching.scoring import score_candidates
from smart_mapper.normalization.pipeline import process_record


@dataclass
class BacktestRow:
    distributor_id: str
    distributor_code: str
    name_raw: str
    address_raw: str
    true_company_customer_id: str


@dataclass
class ThresholdMetric:
    threshold: float
    precision: float
    recall: float
    n_predicted: int
    n_correct: int
    n_true: int


def run_backtest(
    rows: list[BacktestRow],
    customers: list[MasterCustomer],
    weights: MatchingWeights,
    name_synonym_lookup: dict[str, str],
    address_synonym_lookup: dict[str, str],
    city_lookup: dict[str, str],
    candidate_limit: int = 20,
    threshold_sweep: list[float] | None = None,
) -> list[ThresholdMetric]:
    """For every historical (already-known-correct) row, strip away the known
    code-to-code answer and re-run it through the same candidate generation +
    scoring the live pipeline uses, as if the code were unseen. This measures
    real precision/recall of the fuzzy-matching methodology BEFORE trusting it
    with live data, and is what config/thresholds.yaml's values should be
    derived from - not intuition.
    """
    threshold_sweep = threshold_sweep or [round(x * 0.01, 2) for x in range(50, 100)]
    index = CandidateIndex(customers)

    scored_rows: list[tuple[float, bool]] = []
    for row in rows:
        record = process_record(row.name_raw, row.address_raw, name_synonym_lookup, address_synonym_lookup, city_lookup)
        candidates = index.candidates_for(record, candidate_limit)
        if not candidates:
            scored_rows.append((0.0, False))
            continue
        top = score_candidates(record, candidates, weights)[0]
        scored_rows.append((top.composite, top.customer_id == row.true_company_customer_id))

    n_true = len(rows)
    metrics: list[ThresholdMetric] = []
    for threshold in threshold_sweep:
        predicted = [(score, correct) for score, correct in scored_rows if score >= threshold]
        n_predicted = len(predicted)
        n_correct = sum(1 for _, correct in predicted if correct)
        metrics.append(
            ThresholdMetric(
                threshold=threshold,
                precision=(n_correct / n_predicted) if n_predicted else 0.0,
                recall=(n_correct / n_true) if n_true else 0.0,
                n_predicted=n_predicted,
                n_correct=n_correct,
                n_true=n_true,
            )
        )
    return metrics


def recommend_thresholds(metrics: list[ThresholdMetric], target_precision: float = 0.99) -> tuple[float, float]:
    """auto_accept_threshold = lowest score where precision on the backtest
    still meets target_precision (false auto-matches are the costliest
    error). review_lower_threshold = lowest score where the backtest still
    recovers at least one true match (below this, fuzzy matching is no
    better than treating the row as a new-customer candidate).
    """
    if not metrics:
        raise ValueError("No metrics to recommend thresholds from - did the backtest run on zero rows?")

    qualifying = [m for m in metrics if m.n_predicted > 0 and m.precision >= target_precision]
    auto_accept = min((m.threshold for m in qualifying), default=max(m.threshold for m in metrics))

    recovering = [m for m in metrics if m.n_correct > 0]
    review_lower = min((m.threshold for m in recovering), default=min(m.threshold for m in metrics))

    return auto_accept, review_lower


def write_backtest_report(metrics: list[ThresholdMetric], output_path: str | Path) -> None:
    df = pd.DataFrame([m.__dict__ for m in metrics])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)
