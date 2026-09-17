from forgeai.models import PullRequestSnapshot
from forgeai.services.evaluator import EvaluationCase, evaluate


def test_evaluator_reports_per_rule_metrics() -> None:
    clean = PullRequestSnapshot(
        repository="demo/repo",
        pull_request=1,
        title="Docs",
        state="open",
        filenames=["README.md"],
        additions=2,
        deletions=1,
        changed_files=1,
    )
    security = PullRequestSnapshot(
        repository="demo/repo",
        pull_request=2,
        title="Auth",
        state="open",
        filenames=["src/auth/service.py", "tests/test_auth.py"],
        additions=12,
        deletions=3,
        changed_files=2,
    )

    metrics = evaluate(
        [
            EvaluationCase("clean", clean, frozenset()),
            EvaluationCase("security", security, frozenset({"SEC001"})),
        ]
    )

    assert metrics.cases == 2
    assert metrics.exact_match_cases == 1
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
