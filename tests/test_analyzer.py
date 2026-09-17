from forgeai.models import Severity
from forgeai.services.analyzer import analyze
from forgeai.services.github_client import PullRequestSnapshot
from forgeai.services.risk import calculate_score, gate_decision
from forgeai.config import Settings


def snapshot(*paths: str) -> PullRequestSnapshot:
    return PullRequestSnapshot(
        repository="octocat/hello-world",
        pull_request=42,
        title="Change",
        state="open",
        filenames=list(paths),
        additions=10,
        deletions=2,
        changed_files=len(paths),
    )


def test_security_changes_raise_high_severity() -> None:
    findings, factors = analyze(snapshot("src/auth/router.py"))

    assert any(f.severity is Severity.HIGH for f in findings)
    assert calculate_score(factors) >= 30


def test_source_without_tests_adds_test_impact() -> None:
    findings, factors = analyze(snapshot("src/orders/service.py"))

    assert any(f.category == "testing" for f in findings)
    assert any(f.name == "test_impact" for f in factors)


def test_test_changes_suppress_test_impact_warning() -> None:
    findings, factors = analyze(
        snapshot("src/orders/service.py", "tests/test_orders.py")
    )

    assert not any(f.category == "testing" for f in findings)
    assert not any(f.name == "test_impact" for f in factors)


def test_gate_threshold_is_configurable() -> None:
    settings = Settings(risk_gate_threshold=20)
    assert gate_decision(20, settings) == "eligible_for_auto_pass"
    assert gate_decision(21, settings) == "review_required"
