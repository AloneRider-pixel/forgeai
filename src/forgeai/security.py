from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityFinding:
    category: str
    severity: str
    evidence: str


_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("instruction_override", "high", r"ignore\s+(all\s+)?previous\s+instructions"),
    ("instruction_override", "high", r"disregard\s+(all\s+)?previous\s+instructions"),
    (
        "secret_exfiltration",
        "critical",
        r"(?:print|reveal|send|dump)\s+(?:the\s+)?(?:api[_ -]?key|token|secret|password)",
    ),
    (
        "tool_abuse",
        "critical",
        r"(?:run|execute|call)\s+(?:shell|bash|powershell|curl|wget)",
    ),
    ("policy_bypass", "high", r"bypass\s+(?:approval|review|security|policy)"),
    (
        "system_prompt_leak",
        "high",
        r"(?:show|reveal|print)\s+(?:the\s+)?system\s+prompt",
    ),
)


def scan_untrusted_content(text: str) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    for category, severity, pattern in _PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            evidence = match.group(0)[:200]
            findings.append(SecurityFinding(category, severity, evidence))
    return findings


def safe_for_tool_execution(text: str) -> bool:
    findings = scan_untrusted_content(text)
    return not any(item.severity in {"critical", "high"} for item in findings)
