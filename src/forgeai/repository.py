from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from forgeai.control_models import (
    ApprovalResponse,
    ApprovalState,
    EvidenceFinding,
    JobDetailResponse,
    JobStatus,
    ReviewJobResponse,
)
from forgeai.db_models import ApprovalRecord, EvidenceRecord, ReviewJobRecord


class ControlPlaneRepository:
    async def create_job(
        self,
        session: AsyncSession,
        job_id: str,
        repository: str,
        pull_request: int,
        request: dict[str, Any],
    ) -> ReviewJobRecord:
        now = datetime.now(UTC)
        record = ReviewJobRecord(
            id=job_id,
            repository=repository,
            pull_request=pull_request,
            status=JobStatus.QUEUED.value,
            request_json=request,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        await session.commit()
        return record

    async def get_job(self, session: AsyncSession, job_id: str) -> ReviewJobRecord | None:
        result = await session.execute(
            select(ReviewJobRecord)
            .options(selectinload(ReviewJobRecord.evidence), selectinload(ReviewJobRecord.approval))
            .where(ReviewJobRecord.id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_jobs(self, session: AsyncSession, limit: int = 50) -> list[ReviewJobRecord]:
        result = await session.execute(
            select(ReviewJobRecord).order_by(ReviewJobRecord.created_at.desc()).limit(limit)
        )
        return list(result.scalars())

    async def set_running(self, session: AsyncSession, job_id: str) -> None:
        record = await self._require_job(session, job_id)
        record.status = JobStatus.RUNNING.value
        record.updated_at = datetime.now(UTC)
        await session.commit()

    async def set_result(
        self,
        session: AsyncSession,
        job_id: str,
        report: dict[str, Any],
        plan: dict[str, Any] | None,
    ) -> None:
        record = await self._require_job(session, job_id)
        record.status = JobStatus.SUCCEEDED.value
        record.risk_score = int(report["risk_score"])
        record.gate = str(report["gate"])
        record.report_json = report
        record.plan_json = plan
        record.error = None
        record.updated_at = datetime.now(UTC)
        await session.commit()

    async def set_failed(self, session: AsyncSession, job_id: str, error: str) -> None:
        record = await self._require_job(session, job_id)
        record.status = JobStatus.FAILED.value
        record.error = error[:4000]
        record.updated_at = datetime.now(UTC)
        await session.commit()

    async def add_evidence(
        self, session: AsyncSession, job_id: str, findings: list[EvidenceFinding]
    ) -> int:
        await self._require_job(session, job_id)
        for finding in findings:
            session.add(
                EvidenceRecord(
                    job_id=job_id,
                    source=finding.source.value,
                    rule_id=finding.rule_id,
                    severity=finding.severity.value,
                    path=finding.path,
                    message=finding.message,
                )
            )
        await session.commit()
        return len(findings)

    async def upsert_approval(
        self,
        session: AsyncSession,
        job_id: str,
        state: ApprovalState,
        decided_by: str | None = None,
        rationale: str = "",
    ) -> ApprovalRecord:
        await self._require_job(session, job_id)
        result = await session.execute(
            select(ApprovalRecord).where(ApprovalRecord.job_id == job_id)
        )
        approval = result.scalar_one_or_none()
        if approval is None:
            approval = ApprovalRecord(id=str(uuid4()), job_id=job_id)
            session.add(approval)
        approval.state = state.value
        approval.decided_by = decided_by
        approval.rationale = rationale[:2000]
        approval.decided_at = datetime.now(UTC)
        await session.commit()
        return approval

    async def create_execution(
        self,
        session: AsyncSession,
        job_id: str,
        tool_name: str,
        arguments: dict[str, str],
        status: str,
        response: dict[str, Any],
    ) -> str:
        from forgeai.db_models import ExecutionRecord

        execution_id = str(uuid4())
        session.add(
            ExecutionRecord(
                id=execution_id,
                job_id=job_id,
                tool_name=tool_name,
                status=status,
                arguments_json=arguments,
                response_json=response,
            )
        )
        await session.commit()
        return execution_id

    async def _require_job(self, session: AsyncSession, job_id: str) -> ReviewJobRecord:
        record = await session.get(ReviewJobRecord, job_id)
        if record is None:
            raise ValueError(f"review job {job_id} was not found")
        return record

    @staticmethod
    def to_response(record: ReviewJobRecord) -> ReviewJobResponse:
        return ReviewJobResponse(
            job_id=record.id,
            repository=record.repository,
            pull_request=record.pull_request,
            status=JobStatus(record.status),
            risk_score=record.risk_score,
            gate=record.gate,
            error=record.error,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def to_detail(record: ReviewJobRecord) -> JobDetailResponse:
        approval = None
        if record.approval:
            approval = ApprovalResponse(
                approval_id=record.approval.id,
                job_id=record.approval.job_id,
                state=ApprovalState(record.approval.state),
                decided_by=record.approval.decided_by,
                rationale=record.approval.rationale,
            )
        evidence = [
            EvidenceFinding(
                rule_id=item.rule_id,
                severity=item.severity,
                message=item.message,
                path=item.path,
                source=item.source,
            )
            for item in record.evidence
        ]
        return JobDetailResponse(
            **ControlPlaneRepository.to_response(record).model_dump(),
            report=record.report_json,
            plan=record.plan_json,
            evidence=evidence,
            approval=approval,
        )
