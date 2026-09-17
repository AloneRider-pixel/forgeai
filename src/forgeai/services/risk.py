from forgeai.config import Settings
from forgeai.models import Finding, GateDecision, RiskFactor, Severity


def calculate_score(factors: list[RiskFactor]) -> int:
    return min(100, sum(factor.points for factor in factors))


def gate_decision(score: int, settings: Settings, findings: list[Finding] | None = None) -> GateDecision:
    findings = findings or []
    if any(finding.severity is Severity.CRITICAL for finding in findings):
        return GateDecision.REVIEW_REQUIRED
    if score > settings.risk_gate_threshold:
        return GateDecision.REVIEW_REQUIRED
    return GateDecision.ELIGIBLE_FOR_AUTO_PASS


def summarize_findings(findings: list[Finding]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for finding in findings:
        summary[finding.severity.value] = summary.get(finding.severity.value, 0) + 1
    return summary
