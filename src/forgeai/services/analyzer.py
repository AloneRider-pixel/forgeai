import re
from collections.abc import Iterable

from forgeai.models import Finding, PullRequestSnapshot, RiskFactor, Severity

SECURITY_PATHS = re.compile(
    r"(^|/)(auth|security|permissions?|iam|oauth|sso|jwt|secrets?)(/|\.|$)", re.IGNORECASE
)
INFRA_PATHS = re.compile(
    r"(^|/)(\.github/workflows|terraform|k8s|kubernetes|helm|docker|infra|deploy)(/|\.|$)",
    re.IGNORECASE,
)
DATA_PATHS = re.compile(r"(^|/)(migrations?|schema|database|db)(/|\.|$)", re.IGNORECASE)
DEPENDENCY_PATHS = re.compile(
    r"(^|/)(requirements[^/]*\.txt|pyproject\.toml|package(-lock)?\.json|poetry\.lock|"
    r"pnpm-lock\.yaml|yarn\.lock|go\.mod|go\.sum|cargo\.toml|cargo\.lock)$",
    re.IGNORECASE,
)
TEST_PATHS = re.compile(r"(^|/)(tests?|__tests__|spec)(/|\.|$)", re.IGNORECASE)
SECRET_FILES = re.compile(r"(^|/)(\.env(\..*)?|.*\.(pem|key|p12|pfx))$", re.IGNORECASE)
SOURCE_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".go", ".java", ".rs", ".cs", ".rb")


def _matching(paths: Iterable[str], pattern: re.Pattern[str]) -> list[str]:
    return [path for path in paths if pattern.search(path)]


def _add(
    findings: list[Finding],
    factors: list[RiskFactor],
    *,
    rule_id: str,
    severity: Severity,
    category: str,
    title: str,
    detail: str,
    paths: list[str],
    points: int,
    rationale: str,
) -> None:
    findings.append(
        Finding(
            rule_id=rule_id,
            severity=severity,
            category=category,
            title=title,
            detail=detail,
            paths=paths[:25],
        )
    )
    factors.append(RiskFactor(rule_id=rule_id, name=rule_id, points=points, rationale=rationale))


def analyze(snapshot: PullRequestSnapshot) -> tuple[list[Finding], list[RiskFactor]]:
    paths = snapshot.filenames
    findings: list[Finding] = []
    factors: list[RiskFactor] = []

    security_paths = _matching(paths, SECURITY_PATHS)
    if security_paths:
        _add(
            findings,
            factors,
            rule_id="SEC001",
            severity=Severity.HIGH,
            category="security",
            title="Security-sensitive files changed",
            detail="Authentication, authorization, identity, or secret-handling code changed.",
            paths=security_paths,
            points=30,
            rationale="Security-sensitive paths require explicit human review.",
        )

    secret_paths = _matching(paths, SECRET_FILES)
    if secret_paths:
        _add(
            findings,
            factors,
            rule_id="SEC002",
            severity=Severity.CRITICAL,
            category="security",
            title="Secret material or environment files changed",
            detail="The pull request touches credential-bearing or private-key file patterns.",
            paths=secret_paths,
            points=45,
            rationale=(
                "Credential and private-key material can create immediate security exposure."
            ),
        )

    infra_paths = _matching(paths, INFRA_PATHS)
    if infra_paths:
        _add(
            findings,
            factors,
            rule_id="OPS001",
            severity=Severity.MEDIUM,
            category="operations",
            title="Infrastructure or deployment changes",
            detail="CI/CD, container, Kubernetes, Terraform, or deployment code changed.",
            paths=infra_paths,
            points=20,
            rationale="Deployment changes can affect availability and runtime behavior.",
        )

    data_paths = _matching(paths, DATA_PATHS)
    if data_paths:
        _add(
            findings,
            factors,
            rule_id="DATA001",
            severity=Severity.MEDIUM,
            category="data",
            title="Database or schema changes",
            detail="Database schema, migrations, or persistence code changed.",
            paths=data_paths,
            points=15,
            rationale="Data migrations can be difficult to roll back safely.",
        )

    dependency_paths = _matching(paths, DEPENDENCY_PATHS)
    if dependency_paths:
        _add(
            findings,
            factors,
            rule_id="DEP001",
            severity=Severity.MEDIUM,
            category="dependencies",
            title="Dependency manifests or lockfiles changed",
            detail=(
                "Dependency inputs changed; compatibility and supply-chain impact should "
                "be checked."
            ),
            paths=dependency_paths,
            points=10,
            rationale=(
                "Dependency changes can alter runtime behavior or introduce supply-chain "
                "risk."
            ),
        )

    source_paths = [path for path in paths if path.lower().endswith(SOURCE_EXTENSIONS)]
    test_paths = _matching(paths, TEST_PATHS)
    if source_paths and not test_paths:
        _add(
            findings,
            factors,
            rule_id="TEST001",
            severity=Severity.MEDIUM,
            category="testing",
            title="Source changes without visible test changes",
            detail="Production code changed without an obvious test path in the pull request.",
            paths=source_paths,
            points=20,
            rationale="Behavioral changes without accompanying tests deserve additional review.",
        )

    if snapshot.changed_files >= 50 or snapshot.additions + snapshot.deletions >= 1000:
        _add(
            findings,
            factors,
            rule_id="CHG001",
            severity=Severity.MEDIUM,
            category="change_size",
            title="Large pull request surface",
            detail="The pull request changes many files or lines, increasing review complexity.",
            paths=paths,
            points=10,
            rationale="Large changes are harder to reason about and increase review risk.",
        )

    return findings, factors
