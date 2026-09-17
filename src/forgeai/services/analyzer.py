from collections.abc import Iterable
import re

from forgeai.models import Finding, RiskFactor, Severity
from forgeai.services.github_client import PullRequestSnapshot


SECURITY_PATHS = re.compile(
    r"(^|/)(auth|security|permissions?|iam|oauth|sso|jwt|secrets?)(/|\\.|$)",
    re.IGNORECASE,
)
INFRA_PATHS = re.compile(
    r"(^|/)(\\.github/workflows|terraform|k8s|kubernetes|helm|docker|infra|deploy)(/|\\.|$)",
    re.IGNORECASE,
)
DATA_PATHS = re.compile(
    r"(^|/)(migrations?|schema|database|db)(/|\\.|$)",
    re.IGNORECASE,
)
DEPENDENCY_PATHS = re.compile(
    r"(^|/)(requirements[^/]*\\.txt|pyproject\\.toml|package(-lock)?\\.json|poetry\\.lock|"
    r"pnpm-lock\\.yaml|yarn\\.lock|go\\.mod|go\\.sum)$",
    re.IGNORECASE,
)
TEST_PATHS = re.compile(r"(^|/)(tests?|__tests__|spec)(/|\\.|$)", re.IGNORECASE)


def _matching(paths: Iterable[str], pattern: re.Pattern[str]) -> list[str]:
    return [path for path in paths if pattern.search(path)]


def analyze(snapshot: PullRequestSnapshot) -> tuple[list[Finding], list[RiskFactor]]:
    paths = snapshot.filenames
    findings: list[Finding] = []
    factors: list[RiskFactor] = []

    security_paths = _matching(paths, SECURITY_PATHS)
    if security_paths:
        findings.append(
            Finding(
                severity=Severity.HIGH,
                category="security",
                title="Security-sensitive files changed",
                detail="Authentication, authorization, identity, or secret-handling code changed.",
                paths=security_paths,
            )
        )
        factors.append(
            RiskFactor(
                name="security_surface",
                points=30,
                rationale="Security-sensitive paths require explicit human review.",
            )
        )

    infra_paths = _matching(paths, INFRA_PATHS)
    if infra_paths:
        findings.append(
            Finding(
                severity=Severity.MEDIUM,
                category="operations",
                title="Infrastructure or deployment changes",
                detail="CI/CD, container, Kubernetes, Terraform, or deployment code changed.",
                paths=infra_paths,
            )
        )
        factors.append(
            RiskFactor(
                name="infrastructure_change",
                points=20,
                rationale="Deployment changes can affect availability and runtime behavior.",
            )
        )

    data_paths = _matching(paths, DATA_PATHS)
    if data_paths:
        findings.append(
            Finding(
                severity=Severity.MEDIUM,
                category="data",
                title="Database or schema changes",
                detail="Database schema, migrations, or persistence code changed.",
                paths=data_paths,
            )
        )
        factors.append(
            RiskFactor(
                name="data_change",
                points=15,
                rationale="Data migrations can be difficult to roll back safely.",
            )
        )

    dependency_paths = _matching(paths, DEPENDENCY_PATHS)
    if dependency_paths:
        findings.append(
            Finding(
                severity=Severity.MEDIUM,
                category="dependencies",
                title="Dependency files changed",
                detail="Dependency manifests or lockfiles changed; compatibility should be checked.",
                paths=dependency_paths,
            )
        )
        factors.append(
            RiskFactor(
                name="dependency_change",
                points=10,
                rationale="Dependency upgrades can change behavior or introduce supply-chain risk.",
            )
        )

    source_paths = [
        path
        for path in paths
        if path.endswith((".py", ".ts", ".tsx", ".js", ".go", ".java", ".rs"))
    ]
    test_paths = _matching(paths, TEST_PATHS)
    if source_paths and not test_paths:
        findings.append(
            Finding(
                severity=Severity.MEDIUM,
                category="testing",
                title="Source changes without visible test changes",
                detail="Production code changed without an obvious test path in the pull request.",
                paths=source_paths[:25],
            )
        )
        factors.append(
            RiskFactor(
                name="test_impact",
                points=20,
                rationale="Behavioral changes without accompanying tests deserve additional review.",
            )
        )

    return findings, factors
