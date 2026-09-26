from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.run_eval import load_cases


def test_evaluation_dataset_is_versioned_and_nonempty() -> None:
    root = Path(__file__).resolve().parents[1]
    dataset = root / "evals" / "cases.jsonl"
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()

    cases = load_cases(dataset)
    assert cases
    assert len(digest) == 64

    payload = {
        "dataset": str(dataset.relative_to(root)),
        "dataset_sha256": digest,
    }
    assert payload["dataset_sha256"] == hashlib.sha256(dataset.read_bytes()).hexdigest()
