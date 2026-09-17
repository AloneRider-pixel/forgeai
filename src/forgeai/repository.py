from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
from forgeai.db_models import (
    ApprovalRecord,
    EvidenceRecord,
    RepositoryDocumentRecord,
    ReviewJobRecord,
    WebhookDeliveryRecord,
)


class ControlPlaneRepository:
    async def create_job(
        self,
        session: AsyncSession,
        job_id: str,
        repository: str,
        pull_request: int,
        request: dict[str, Any],
        *,
        commit: bool = True,
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
        if commit:
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

    async def upsert_repository_documents(
        self,
        session: AsyncSession,
        repository: str,
        ref: str,
        documents: list[dict[str, Any]],
    ) -> int:
        count = 0
        now = datetime.now(UTC)
        for item in documents:
            path = str(item["path"])
            result = await session.execute(
                select(RepositoryDocumentRecord).where(
                    RepositoryDocumentRecord.repository == repository,
                    RepositoryDocumentRecord.ref == ref,
                    RepositoryDocumentRecord.path == path,
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                record = RepositoryDocumentRecord(
                    repository=repository,
                    ref=ref,
                    path=path,
                    sha=str(item.get("sha", "")),
                    content=str(item.get("content", "")),
                    embedding_json=list(item.get("embedding", [])),
                    updated_at=now,
                )
                session.add(record)
            else:
                record.sha = str(item.get("sha", ""))
                record.content = str(item.get("content", ""))
                record.embedding_json = list(item.get("embedding", []))
                record.updated_at = now
            count += 1
        await session.commit()
        return count

    async def list_repository_documents(
        self, session: AsyncSession, repository: str, ref: str, limit: int = 1000
    ) -> list[RepositoryDocumentRecord]:
        result = await session.execute(
            select(RepositoryDocumentRecord)
            .where(
                RepositoryDocumentRecord.repository == repository,
                RepositoryDocumentRecord.ref == ref,
            )
            .order_by(RepositoryDocumentRecord.path.asc())
            .limit(limit)
        )
        return list(result.scalars())

    async def get_webhook_delivery(
        self, session: AsyncSession, delivery_id: str
    ) -> WebhookDeliveryRecord | None:
        result = await session.execute(
            select(WebhookDeliveryRecord)
            .options(selectinload(WebhookDeliveryRecord.job))
            .where(WebhookDeliveryRecord.delivery_id == delivery_id)
        )
        return result.scalar_one_or_none()

    async def create_webhook_delivery(
        self,
        session: AsyncSession,
        delivery_id: str,
        event_type: str,
        action: str,
        repository: str,
        pull_request: int | None,
        payload: dict[str, Any],
        status: str,
        job_id: str | None = None,
        *,
        commit: bool = True,
    ) -> WebhookDeliveryRecord:
        now = datetime.now(UTC)
        record = WebhookDeliveryRecord(
            delivery_id=delivery_id,
            event_type=event_type,
            action=action,
            repository=repository,
            pull_request=pull_request,
            payload_json=payload,
            status=status,
            job_id=job_id,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        if commit:
            await session.commit()
        return record

    async def create_webhook_delivery_idempotent(
        self,
        session: AsyncSession,
        delivery_id: str,
        event_type: str,
        action: str,
        repository: str,
        pull_request: int | None,
        payload: dict[str, Any],
        status: str,
        job_id: str | None = None,
    ) -> tuple[WebhookDeliveryRecord, bool]:
        existing = await self.get_webhook_delivery(session, delivery_id)
        if existing is not None:
            return existing, False
        try:
            record = await self.create_webhook_delivery(
                session,
                delivery_id,
                event_type,
                action,
                repository,
                pull_request,
                payload,
                status,
                job_id,
            )
            return record, True
        except IntegrityError:
            await session.rollback()
            existing = await self.get_webhook_delivery(session, delivery_id)
            if existing is None:
                raise
            return existing, False

    async def list_pending_webhook_deliveries(
        self, session: AsyncSession, limit: int = 20
    ) -> list[WebhookDeliveryRecord]:
        result = await session.execute(
            select(WebhookDeliveryRecord)
            .where(WebhookDeliveryRecord.status == "pending")
            .order_by(WebhookDeliveryRecord.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars())

    async def mark_webhook_enqueued(self, session: AsyncSession, delivery_id: str) -> None:
        record = await self._require_webhook_delivery(session, delivery_id)
        record.status = "enqueued"
        record.attempts += 1
        record.updated_at = datetime.now(UTC)
        record.last_error = None
        await session.commit()

    async def mark_webhook_dispatch_failure(
        self, session: AsyncSession, delivery_id: str, error: str, max_attempts: int
    ) -> None:
        record = await self._require_webhook_delivery(session, delivery_id)
        record.attempts += 1
        record.last_error = error[:4000]
        record.updated_at = datetime.now(UTC)
        if record.attempts >= max_attempts:
            record.status = "dead_lettered"
            if record.job_id:
                job = await self._require_job(session, record.job_id)
                job.status = JobStatus.FAILED.value
                job.error = f"webhook dispatch exhausted retries: {error}"[:4000]
                job.updated_at = datetime.now(UTC)
        await session.commit()

    async def mark_webhook_completed(self, session: AsyncSession, delivery_id: str) -> None:
        record = await self._require_webhook_delivery(session, delivery_id)
        record.status = "completed"
        record.updated_at = datetime.now(UTC)
        record.completed_at = datetime.now(UTC)
        record.last_error = None
        await session.commit()

    async def mark_webhook_failed(
        self, session: AsyncSession, delivery_id: str, error: str
    ) -> None:
        record = await self._require_webhook_delivery(session, delivery_id)
        record.status = "failed"
        record.last_error = error[:4000]
        record.updated_at = datetime.now(UTC)
        await session.commit()

    async def _require_webhook_delivery(
        self, session: AsyncSession, delivery_id: str
    ) -> WebhookDeliveryRecord:
        record = await session.get(WebhookDeliveryRecord, delivery_id)
        if record is None:
            raise ValueError(f"webhook delivery {delivery_id} was not found")
        return record

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
