from forgeai.config import Settings
from forgeai.models import GateDecision, PullRequestSnapshot, Severity
from forgeai.services.analyzer import analyze
from forgeai.services.risk import calculate_score, gate_decision


def snapshot(*paths: str, additions: int = 10, deletions: int = 2) -> PullRequestSnapshot:
    return PullRequestSnapshot(
        repository="octocat/hello-world",
        pull_request=42,
        title="Change",
        state="open",
        filenames=list(paths),
        additions=additions,
        deletions=deletions,
        changed_files=len(paths),
    )


def test_security_changes_raise_high_severity() -> None:
    findings, factors = analyze(snapshot("src/auth/router.py"))

    assert any(f.rule_id == "SEC001" and f.severity is Severity.HIGH for f in findings)
    assert calculate_score(factors) >= 30


def test_secret_material_is_critical() -> None:
    findings, factors = analyze(snapshot(".env.production"))

    assert any(f.rule_id == "SEC002" and f.severity is Severity.CRITICAL for f in findings)
    assert calculate_score(factors) >= 45


def test_source_without_tests_adds_test_impact() -> None:
    findings, factors = analyze(snapshot("src/orders/service.py"))

    assert any(f.rule_id == "TEST001" for f in findings)
    assert any(f.name == "TEST001" for f in factors)


def test_test_changes_suppress_test_impact_warning() -> None:
    findings, factors = analyze(snapshot("src/orders/service.py", "tests/test_orders.py"))

    assert not any(f.rule_id == "TEST001" for f in findings)
    assert not any(f.name == "TEST001" for f in factors)


def test_large_change_surface_is_reported() -> None:
    paths = [f"src/module_{index}.py" for index in range(50)]
    findings, _ = analyze(snapshot(*paths))

    assert any(f.rule_id == "CHG001" for f in findings)


def test_gate_threshold_is_configurable() -> None:
    settings = Settings(risk_gate_threshold=20)

    assert gate_decision(20, settings) is GateDecision.ELIGIBLE_FOR_AUTO_PASS
    assert gate_decision(21, settings) is GateDecision.REVIEW_REQUIRED


def test_critical_finding_always_requires_review() -> None:
    findings, factors = analyze(snapshot(".env"))
    gate = gate_decision(calculate_score(factors), Settings(risk_gate_threshold=100), findings)

    assert gate is GateDecision.REVIEW_REQUIRED
