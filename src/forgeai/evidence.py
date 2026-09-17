from collections.abc import Iterable

from forgeai.control_models import EvidenceFinding
from forgeai.models import GateDecision, Severity


def effective_gate(
    baseline: str | GateDecision, evidence: Iterable[EvidenceFinding]
) -> GateDecision:
    baseline_gate = GateDecision(baseline)
    if baseline_gate is GateDecision.REVIEW_REQUIRED:
        return baseline_gate
    if any(item.severity in {Severity.HIGH, Severity.CRITICAL} for item in evidence):
        return GateDecision.REVIEW_REQUIRED
    return GateDecision.ELIGIBLE_FOR_AUTO_PASS
