from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
import os

from forgeai.security import safe_for_tool_execution, scan_untrusted_content


CASES = Path(__file__).parents[1] / 'evals' / 'security_cases.json'


def main() -> None:
    parser = argparse.ArgumentParser(description='Run deterministic ForgeAI security evaluation.')
    parser.add_argument('--output', type=Path, help='Optional JSON evidence output path.')
    args = parser.parse_args()

    cases = json.loads(CASES.read_text(encoding='utf-8'))
    failures: list[str] = []
    for case in cases:
        findings = scan_untrusted_content(case['text'])
        detected = bool(findings)
        expected = case['name'] != 'benign'
        if detected != expected:
            failures.append(f"{case['name']}: detection mismatch")
        if case['name'] != 'benign' and safe_for_tool_execution(case['text']):
            failures.append(f"{case['name']}: unsafe content was marked executable")
        if case['name'] == 'benign' and not safe_for_tool_execution(case['text']):
            failures.append('benign: content was incorrectly blocked')
    if failures:
        raise SystemExit('security evaluation failed: ' + '; '.join(failures))

    payload = {
        'evaluation': 'deterministic-security-corpus',
        'dataset': str(CASES.relative_to(CASES.parents[1])),
        'cases': len(cases),
        'passed': True,
        'commit': os.getenv('GITHUB_SHA'),
        'generated_at_utc': datetime.now(UTC).isoformat(),
    }
    print(f"security evaluation passed: {len(cases)} cases")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()