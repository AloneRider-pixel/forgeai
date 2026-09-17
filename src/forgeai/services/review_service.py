from __future__ import annotations

import asyncio

from forgeai.config import Settings
from forgeai.control_models import (
    ApprovalState,
    EvidenceFinding,
    JobStatus,
    ReviewJobRequest,
    new_job_id,
)
from forgeai.db import Database
from forgeai.evidence import effective_gate
from forgeai.repository import ControlPlaneRepository
from forgeai.services.context import collect_context
from forgeai.services.github_client import GitHubClient
from forgeai.services.planner import DeterministicPlanner, OpenAICompatiblePlanner
from forgeai.services.review_engine import build_report


class ReviewService:
    def __init__(self, database: Database, github: GitHubClient, settings: Settings) -> None:
        self.database = database
        self.github = github
        self.settings = settings
        self.repository = ControlPlaneRepository()

    async def create_job(self, request: ReviewJobRequest) -> str:
        job_id = new_job_id()
        async with self.database.sessions() as session:
            record = await self.repository.create_job(
                session,
                job_id,
                request.repository,
                request.pull_request,
                request.model_dump(mode="json"),
            )
            return record.id

    async def process(self, job_id: str) -> None:
        async with self.database.sessions() as session:
            record = await self.repository.get_job(session, job_id)
            if record is None or record.status != JobStatus.QUEUED.value:
                return
            request = ReviewJobRequest.model_validate(record.request_json)
            await self.repository.set_running(session, job_id)

        try:
            snapshot, changed_files = await asyncio.to_thread(
                self.github.get_pull_request_bundle,
                request.repository,
                request.pull_request,
            )
            baseline = await asyncio.to_thread(build_report, snapshot, self.settings)
            context = await asyncio.to_thread(
                collect_context,
                self.github,
                snapshot,
                changed_files,
                baseline.findings,
                request.max_context_files,
                request.max_file_chars,
            )
            planner = OpenAICompatiblePlanner(self.settings) if request.use_llm else DeterministicPlanner()
            plan = await asyncio.to_thread(planner.plan, baseline, context)

            async with self.database.sessions() as session:
                await self.repository.set_result(
                    session,
                    job_id,
                    baseline.model_dump(mode="json"),
                    plan.model_dump(mode="json"),
                )
                if request.delivery_id:
                    await self.repository.mark_webhook_completed(session, request.delivery_id)
                record = await self.repository.get_job(session, job_id)
                if record and record.gate == "review_required":
                    await self.repository.upsert_approval(session, job_id, ApprovalState.PENDING)
        except Exception as exc:
            async with self.database.sessions() as session:
                await self.repository.set_failed(session, job_id, str(exc))
                if request.delivery_id:
                    await self.repository.mark_webhook_failed(session, request.delivery_id, str(exc))
            raise

    async def add_evidence_and_recompute_gate(
        self, job_id: str, findings: list[EvidenceFinding]
    ) -> None:
        async with self.database.sessions() as session:
            await self.repository.add_evidence(session, job_id, findings)
            record = await self.repository.get_job(session, job_id)
            if record is None or record.report_json is None:
                return
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
            gate = effective_gate(record.report_json["gate"], evidence)
            record.gate = gate.value
            updated_report = dict(record.report_json)
            updated_report["gate"] = gate.value
            record.report_json = updated_report
            if gate.value == "review_required":
                await self.repository.upsert_approval(session, job_id, ApprovalState.PENDING)
            else:
                await session.commit()
