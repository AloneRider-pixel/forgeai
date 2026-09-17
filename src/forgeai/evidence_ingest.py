from __future__ import annotations

from forgeai.control_models import EvidenceFinding, EvidenceSource, Severity


def _severity(level: object) -> Severity:
    value = str(level or "warning").lower()
    if value in {"error", "critical"}:
        return Severity.CRITICAL
    if value in {"warning", "high"}:
        return Severity.HIGH
    if value in {"note", "medium"}:
        return Severity.MEDIUM
    return Severity.LOW


def _message(result: dict[str, object]) -> str:
    message = result.get("message")
    if isinstance(message, dict) and isinstance(message.get("text"), str):
        return message["text"][:2000]
    return "External analysis reported a finding."


def _path(result: dict[str, object]) -> str | None:
    locations = result.get("locations")
    if not isinstance(locations, list) or not locations:
        return None
    first = locations[0]
    if not isinstance(first, dict):
        return None
    physical = first.get("physicalLocation")
    if not isinstance(physical, dict):
        return None
    artifact = physical.get("artifactLocation")
    if not isinstance(artifact, dict) or not isinstance(artifact.get("uri"), str):
        return None
    return artifact["uri"][:1000]


def parse_sarif(payload: dict[str, object], source: EvidenceSource) -> list[EvidenceFinding]:
    findings: list[EvidenceFinding] = []
    runs = payload.get("runs")
    if not isinstance(runs, list):
        return findings
    for run in runs:
        if not isinstance(run, dict):
            continue
        results = run.get("results")
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            rule_id = str(result.get("ruleId") or "external.unknown")[:120]
            findings.append(
                EvidenceFinding(
                    rule_id=rule_id,
                    severity=_severity(result.get("level")),
                    message=_message(result),
                    path=_path(result),
                    source=source,
                )
            )
            if len(findings) >= 500:
                return findings
    return findings
