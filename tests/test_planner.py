from forgeai.models import ContextSnippet, PullRequestSnapshot, ReviewReport
from forgeai.services.planner import DeterministicPlanner, OpenAICompatiblePlanner
from forgeai.config import Settings
from forgeai.services.analyzer import analyze
from forgeai.services.risk import calculate_score, gate_decision


def _report() -> ReviewReport:
    snapshot = PullRequestSnapshot(
        repository="octocat/hello-world",
        pull_request=42,
        title="Add authentication flow",
        state="open",
        filenames=["src/auth/router.py"],
        additions=20,
        deletions=2,
        changed_files=1,
    )
    findings, factors = analyze(snapshot)
    return ReviewReport(
        snapshot=snapshot,
        risk_score=calculate_score(factors),
        gate=gate_decision(calculate_score(factors), Settings(), findings),
        findings=findings,
        factors=factors,
    )


def test_deterministic_planner_is_explainable() -> None:
    report = _report()
    plan = DeterministicPlanner().plan(
        report,
        [
            ContextSnippet(
                path="src/auth/router.py",
                content="def login(): ...",
                relevance=0.8,
            )
        ],
    )

    assert plan.provider == "deterministic"
    assert any("authorization" in item.lower() for item in plan.risk_questions)
    assert 0.0 <= plan.confidence <= 1.0


def test_llm_planner_falls_back_without_configuration() -> None:
    report = _report()
    plan = OpenAICompatiblePlanner(Settings()).plan(report, [])

    assert plan.provider == "deterministic"
