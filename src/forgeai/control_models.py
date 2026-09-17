from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

from forgeai.models import Severity


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class EvidenceSource(StrEnum):
    CODEQL = "codeql"
    DEPENDENCY_REVIEW = "dependency-review"


class EvidenceFinding(BaseModel):
    rule_id: str
    severity: Severity
    message: str = Field(min_length=1, max_length=2000)
    path: str | None = None
    source: EvidenceSource


class EvidenceBatchRequest(BaseModel):
    findings: list[EvidenceFinding] = Field(default_factory=list, max_length=500)


class ReviewJobRequest(BaseModel):
    repository: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")
    pull_request: int = Field(gt=0)
    use_llm: bool = False
    max_context_files: int = Field(default=5, ge=1, le=10)
    max_file_chars: int = Field(default=12000, ge=1000, le=20000)


class ReviewJobResponse(BaseModel):
    job_id: str
    repository: str
    pull_request: int
    status: JobStatus
    risk_score: int | None = None
    gate: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class ApprovalDecisionRequest(BaseModel):
    decided_by: str = Field(min_length=1, max_length=120)
    rationale: str = Field(default="", max_length=2000)


class ApprovalResponse(BaseModel):
    approval_id: str
    job_id: str
    state: ApprovalState
    decided_by: str | None = None
    rationale: str = ""


class ExecutionRequest(BaseModel):
    tool_name: str = Field(pattern=r"^[a-z0-9_.-]{3,100}$")
    arguments: dict[str, str] = Field(default_factory=dict, max_length=20)


class ExecutionResponse(BaseModel):
    execution_id: str
    job_id: str
    tool_name: str
    status: str
    response: dict[str, object] = Field(default_factory=dict)


class JobDetailResponse(ReviewJobResponse):
    report: dict[str, object] | None = None
    plan: dict[str, object] | None = None
    evidence: list[EvidenceFinding] = Field(default_factory=list)
    approval: ApprovalResponse | None = None


def new_job_id() -> str:
    return str(uuid4())
