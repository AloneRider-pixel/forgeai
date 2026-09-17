from __future__ import annotations

import json
from pathlib import Path

from forgeai.security import safe_for_tool_execution, scan_untrusted_content


CASES = Path(__file__).parents[1] / "evals" / "security_cases.json"


def main() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    failures: list[str] = []
    for case in cases:
        findings = scan_untrusted_content(case["text"])
        detected = bool(findings)
        expected = case["name"] != "benign"
        if detected != expected:
            failures.append(f"{case['name']}: detection mismatch")
        if case["name"] != "benign" and safe_for_tool_execution(case["text"]):
            failures.append(f"{case['name']}: unsafe content was marked executable")
        if case["name"] == "benign" and not safe_for_tool_execution(case["text"]):
            failures.append("benign: content was incorrectly blocked")
    if failures:
        raise SystemExit("security evaluation failed: " + "; ".join(failures))
    print(f"security evaluation passed: {len(cases)} cases")


if __name__ == "__main__":
    main()
