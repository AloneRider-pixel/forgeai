from __future__ import annotations

from dataclasses import dataclass

from forgeai.models import PullRequestSnapshot
from forgeai.services.analyzer import analyze


@dataclass(frozen=True)
class EvaluationCase:
    name: str
    snapshot: PullRequestSnapshot
    expected_rule_ids: frozenset[str]


@dataclass(frozen=True)
class EvaluationMetrics:
    cases: int
    exact_match_cases: int
    precision: float
    recall: float


def evaluate(cases: list[EvaluationCase]) -> EvaluationMetrics:
    if not cases:
        return EvaluationMetrics(0, 0, 1.0, 1.0)

    true_positive = 0
    predicted_total = 0
    expected_total = 0
    exact = 0
    for case in cases:
        findings, _ = analyze(case.snapshot)
        predicted = {finding.rule_id for finding in findings}
        true_positive += len(predicted & case.expected_rule_ids)
        predicted_total += len(predicted)
        expected_total += len(case.expected_rule_ids)
        exact += predicted == set(case.expected_rule_ids)

    precision = true_positive / predicted_total if predicted_total else 1.0
    recall = true_positive / expected_total if expected_total else 1.0
    return EvaluationMetrics(
        cases=len(cases),
        exact_match_cases=exact,
        precision=precision,
        recall=recall,
    )
