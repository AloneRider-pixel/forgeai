from forgeai.config import Settings
from forgeai.models import Finding, RiskFactor


def calculate_score(factors: list[RiskFactor]) -> int:
    return min(100, sum(factor.points for factor in factors))


def gate_decision(score: int, settings: Settings) -> str:
    return "review_required" if score > settings.risk_gate_threshold else "eligible_for_auto_pass"


def summarize_findings(findings: list[Finding]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for finding in findings:
        summary[finding.severity.value] = summary.get(finding.severity.value, 0) + 1
    return summary
