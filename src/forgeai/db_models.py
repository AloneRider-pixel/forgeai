from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forgeai.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ReviewJobRecord(Base):
    __tablename__ = "review_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository: Mapped[str] = mapped_column(String(200), index=True)
    pull_request: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gate: Mapped[str | None] = mapped_column(String(50), nullable=True)
    request_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    report_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    plan_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    evidence: Mapped[list[EvidenceRecord]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    approval: Mapped[ApprovalRecord | None] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
    executions: Mapped[list[ExecutionRecord]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    webhook_deliveries: Mapped[list[WebhookDeliveryRecord]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class EvidenceRecord(Base):
    __tablename__ = "review_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("review_jobs.id"), index=True)
    source: Mapped[str] = mapped_column(String(50))
    rule_id: Mapped[str] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(30))
    path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[ReviewJobRecord] = relationship(back_populates="evidence")


class ApprovalRecord(Base):
    __tablename__ = "review_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("review_jobs.id"), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(30), default="pending")
    decided_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[ReviewJobRecord] = relationship(back_populates="approval")


class ExecutionRecord(Base):
    __tablename__ = "review_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("review_jobs.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30))
    arguments_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[ReviewJobRecord] = relationship(back_populates="executions")


class WebhookDeliveryRecord(Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (UniqueConstraint("delivery_id", name="uq_webhook_delivery_id"),)

    delivery_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(80), default="")
    repository: Mapped[str] = mapped_column(String(200), index=True)
    pull_request: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), index=True)
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("review_jobs.id"), nullable=True, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[ReviewJobRecord | None] = relationship(back_populates="webhook_deliveries")
