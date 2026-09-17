from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Any

from forgeai.config import Settings
from forgeai.control_models import ReviewJobRequest, new_job_id
from forgeai.db import Database
from forgeai.repository import ControlPlaneRepository
from forgeai.queue import JobQueue

SUPPORTED_ACTIONS = frozenset({"opened", "reopened", "synchronize", "ready_for_review"})
_DELIVERY_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,128}$")


class WebhookValidationError(ValueError):
    """Raised when a GitHub delivery cannot be trusted or normalized."""


@dataclass(frozen=True)
class PullRequestEvent:
    delivery_id: str
    event_type: str
    action: str
    repository: str
    pull_request: int


def verify_signature(payload: bytes, signature: str | None, secret: str | None) -> None:
    if not secret:
        raise WebhookValidationError("GITHUB_WEBHOOK_SECRET is not configured")
    if not signature or not signature.startswith("sha256="):
        raise WebhookValidationError("missing or invalid X-Hub-Signature-256")
    supplied = signature.removeprefix("sha256=").strip()
    if len(supplied) != 64:
        raise WebhookValidationError("invalid webhook signature length")
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise WebhookValidationError("invalid webhook signature")


def normalize_pull_request_event(
    delivery_id: str, event_type: str, payload: dict[str, Any]
) -> PullRequestEvent | None:
    if not _DELIVERY_ID_RE.fullmatch(delivery_id):
        raise WebhookValidationError("invalid X-GitHub-Delivery")
    if event_type != "pull_request":
        return None
    action = payload.get("action")
    if action not in SUPPORTED_ACTIONS:
        return None

    repository = payload.get("repository")
    pull_request = payload.get("pull_request")
    if not isinstance(repository, dict) or not isinstance(pull_request, dict):
        raise WebhookValidationError("pull_request payload is missing required objects")
    full_name = repository.get("full_name")
    number = pull_request.get("number")
    if not isinstance(full_name, str) or not isinstance(number, int) or number <= 0:
        raise WebhookValidationError("pull_request payload is missing repository or number")

    request = ReviewJobRequest(repository=full_name, pull_request=number)
    return PullRequestEvent(
        delivery_id=delivery_id,
        event_type=event_type,
        action=action,
        repository=request.repository,
        pull_request=request.pull_request,
    )


class GitHubWebhookService:
    def __init__(self, database: Database, queue: JobQueue, settings: Settings) -> None:
        self.database = database
        self.queue = queue
        self.settings = settings
        self.repository = ControlPlaneRepository()

    async def ingest(
        self,
        delivery_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        event = normalize_pull_request_event(delivery_id, event_type, payload)
        async with self.database.sessions() as session:
            existing = await self.repository.get_webhook_delivery(session, delivery_id)
            if existing is not None:
                return {
                    "accepted": existing.status not in {"ignored", "dead_lettered"},
                    "duplicate": True,
                    "delivery_id": delivery_id,
                    "status": existing.status,
                    "job_id": existing.job_id,
                }

            if event is None:
                await self.repository.create_webhook_delivery(
                    session,
                    delivery_id,
                    event_type,
                    str(payload.get("action", "")),
                    "",
                    None,
                    payload,
                    "ignored",
                )
                return {
                    "accepted": False,
                    "duplicate": False,
                    "delivery_id": delivery_id,
                    "status": "ignored",
                    "job_id": None,
                }

            job_id = new_job_id()
            job_request = ReviewJobRequest(
                repository=event.repository,
                pull_request=event.pull_request,
                trigger_source=f"github:{event.event_type}:{event.action}",
                delivery_id=delivery_id,
            )
            await self.repository.create_job(
                session,
                job_id,
                event.repository,
                event.pull_request,
                job_request.model_dump(mode="json"),
                commit=False,
            )
            await self.repository.create_webhook_delivery(
                session,
                delivery_id,
                event.event_type,
                event.action,
                event.repository,
                event.pull_request,
                payload,
                "pending",
                job_id=job_id,
                commit=False,
            )
            await session.commit()

        return {
            "accepted": True,
            "duplicate": False,
            "delivery_id": delivery_id,
            "status": "pending",
            "job_id": job_id,
        }


class WebhookDispatcher:
    def __init__(self, database: Database, queue: JobQueue, settings: Settings) -> None:
        self.database = database
        self.queue = queue
        self.settings = settings
        self.repository = ControlPlaneRepository()

    async def dispatch_pending_once(self, limit: int = 20) -> int:
        async with self.database.sessions() as session:
            deliveries = await self.repository.list_pending_webhook_deliveries(session, limit)

        dispatched = 0
        for delivery in deliveries:
            if not delivery.job_id:
                continue
            try:
                await self.queue.enqueue(delivery.job_id)
            except Exception as exc:
                async with self.database.sessions() as session:
                    await self.repository.mark_webhook_dispatch_failure(
                        session,
                        delivery.delivery_id,
                        str(exc),
                        self.settings.webhook_dispatch_max_attempts,
                    )
                continue

            async with self.database.sessions() as session:
                await self.repository.mark_webhook_enqueued(session, delivery.delivery_id)
            dispatched += 1
        return dispatched

    async def run_forever(self, stop_event) -> None:
        while not stop_event.is_set():
            await self.dispatch_pending_once()
            try:
                await asyncio_wait(stop_event, self.settings.webhook_dispatch_interval_seconds)
            except TimeoutError:
                continue


async def asyncio_wait(stop_event, timeout: float) -> None:
    import asyncio

    try:
        await asyncio.wait_for(stop_event.wait(), timeout=max(timeout, 0.1))
    except asyncio.TimeoutError as exc:
        raise TimeoutError from exc
