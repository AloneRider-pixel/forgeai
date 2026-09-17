from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GateDecision(StrEnum):
    REVIEW_REQUIRED = "review_required"
    ELIGIBLE_FOR_AUTO_PASS = "eligible_for_auto_pass"


class Finding(BaseModel):
    rule_id: str
    severity: Severity
    category: str
    title: str
    detail: str
    paths: list[str] = Field(default_factory=list)


class RiskFactor(BaseModel):
    rule_id: str
    name: str
    points: int = Field(ge=0, le=100)
    rationale: str


class PullRequestRequest(BaseModel):
    repository: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")
    pull_request: int = Field(gt=0)


class PullRequestSnapshot(BaseModel):
    repository: str
    pull_request: int
    title: str
    state: str
    draft: bool = False
    filenames: list[str] = Field(default_factory=list)
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    changed_files: int = Field(ge=0)


class ReviewReport(BaseModel):
    snapshot: PullRequestSnapshot
    risk_score: int = Field(ge=0, le=100)
    gate: GateDecision
    findings: list[Finding] = Field(default_factory=list)
    factors: list[RiskFactor] = Field(default_factory=list)

    @property
    def finding_summary(self) -> dict[str, int]:
        summary: dict[str, int] = {}
        for finding in self.findings:
            summary[finding.severity.value] = summary.get(finding.severity.value, 0) + 1
        return summary
