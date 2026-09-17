from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Finding(BaseModel):
    severity: Severity
    category: str
    title: str
    detail: str
    paths: list[str] = Field(default_factory=list)


class RiskFactor(BaseModel):
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
    filenames: list[str] = Field(default_factory=list)
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    changed_files: int = Field(ge=0)


class ReviewReport(BaseModel):
    snapshot: PullRequestSnapshot
    risk_score: int = Field(ge=0, le=100)
    gate: str
    findings: list[Finding] = Field(default_factory=list)
    factors: list[RiskFactor] = Field(default_factory=list)
