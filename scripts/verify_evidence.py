"""Validate that published evaluation artifacts contain complete provenance and sane metrics."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

HEX64 = set("0123456789abcdef")


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read evidence artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"Evidence artifact must be a JSON object: {path}")
    return value


def require_sha(value: object, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or set(value.lower()) - HEX64:
        raise SystemExit(f"{label} must be a 64-character SHA-256 digest")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--security", type=Path, required=True)
    args = parser.parse_args()

    benchmark = load(args.benchmark)
    security = load(args.security)

    if benchmark.get("evaluation") != "deterministic-rule-engine":
        raise SystemExit("Unexpected benchmark evaluation type")
    cases = benchmark.get("cases")
    exact = benchmark.get("exact_match_cases")
    valid_counts = (
        isinstance(cases, int)
        and cases > 0
        and isinstance(exact, int)
        and 0 <= exact <= cases
    )
    if not valid_counts:
        raise SystemExit("Benchmark case counts are invalid")
    for key in ("precision", "recall", "exact_match_rate"):
        value = benchmark.get(key)
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise SystemExit(f"Benchmark metric {key} must be between 0 and 1")
    require_sha(benchmark.get("dataset_sha256"), "benchmark.dataset_sha256")
    if not benchmark.get("generated_at_utc"):
        raise SystemExit("Benchmark is missing generated_at_utc")
    require_commit = os.getenv("GITHUB_ACTIONS") == "true"
    if require_commit and not benchmark.get("commit"):
        raise SystemExit("Benchmark is missing the CI commit SHA")

    if security.get("evaluation") != "deterministic-security-corpus":
        raise SystemExit("Unexpected security evaluation type")
    security_cases = security.get("cases")
    if not isinstance(security_cases, int) or security_cases <= 0:
        raise SystemExit("Security case count is invalid")
    if security.get("passed") is not True:
        raise SystemExit("Security evaluation is not marked passed")
    if not security.get("generated_at_utc"):
        raise SystemExit("Security evidence is missing generated_at_utc")
    if require_commit and not security.get("commit"):
        raise SystemExit("Security evidence is missing the CI commit SHA")

    print(
        f"evaluation evidence verified: benchmark_cases={cases}, "
        f"exact_match_rate={benchmark['exact_match_rate']:.3f}, "
        f"security_cases={security_cases}"
    )


if __name__ == "__main__":
    main()
