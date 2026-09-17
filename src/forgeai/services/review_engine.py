from __future__ import annotations

from forgeai.config import Settings
from forgeai.models import PullRequestSnapshot, ReviewReport
from forgeai.services.analyzer import analyze
from forgeai.services.risk import calculate_score, gate_decision


def build_report(snapshot: PullRequestSnapshot, settings: Settings) -> ReviewReport:
    findings, factors = analyze(snapshot)
    score = calculate_score(factors)
    return ReviewReport(
        snapshot=snapshot,
        risk_score=score,
        gate=gate_decision(score, settings, findings),
        findings=findings,
        factors=factors,
    )
