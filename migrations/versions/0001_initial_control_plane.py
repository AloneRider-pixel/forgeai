from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("repository", sa.String(length=200), nullable=False),
        sa.Column("pull_request", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("gate", sa.String(length=50), nullable=True),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=True),
        sa.Column("plan_json", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_jobs_repository", "review_jobs", ["repository"])
    op.create_index("ix_review_jobs_pull_request", "review_jobs", ["pull_request"])
    op.create_index("ix_review_jobs_status", "review_jobs", ["status"])

    op.create_table(
        "review_evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("rule_id", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("path", sa.String(length=1000), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["review_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_evidence_job_id", "review_evidence", ["job_id"])

    op.create_table(
        "review_approvals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("decided_by", sa.String(length=120), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["review_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index("ix_review_approvals_job_id", "review_approvals", ["job_id"])

    op.create_table(
        "review_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("arguments_json", sa.JSON(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["review_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_executions_job_id", "review_executions", ["job_id"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("delivery_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("repository", sa.String(length=200), nullable=False),
        sa.Column("pull_request", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["review_jobs.id"]),
        sa.PrimaryKeyConstraint("delivery_id"),
        sa.UniqueConstraint("delivery_id", name="uq_webhook_delivery_id"),
    )
    op.create_index("ix_webhook_deliveries_event_type", "webhook_deliveries", ["event_type"])
    op.create_index("ix_webhook_deliveries_repository", "webhook_deliveries", ["repository"])
    op.create_index("ix_webhook_deliveries_status", "webhook_deliveries", ["status"])
    op.create_index("ix_webhook_deliveries_job_id", "webhook_deliveries", ["job_id"])

    op.create_table(
        "repository_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repository", sa.String(length=200), nullable=False),
        sa.Column("ref", sa.String(length=200), nullable=False),
        sa.Column("path", sa.String(length=1000), nullable=False),
        sa.Column("sha", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository", "ref", "path", name="uq_repository_document"),
    )
    op.create_index("ix_repository_documents_repository", "repository_documents", ["repository"])
    op.create_index("ix_repository_documents_ref", "repository_documents", ["ref"])


def downgrade() -> None:
    op.drop_index("ix_repository_documents_ref", table_name="repository_documents")
    op.drop_index("ix_repository_documents_repository", table_name="repository_documents")
    op.drop_table("repository_documents")
    op.drop_index("ix_webhook_deliveries_job_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_status", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_repository", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_event_type", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_review_executions_job_id", table_name="review_executions")
    op.drop_table("review_executions")
    op.drop_index("ix_review_approvals_job_id", table_name="review_approvals")
    op.drop_table("review_approvals")
    op.drop_index("ix_review_evidence_job_id", table_name="review_evidence")
    op.drop_table("review_evidence")
    op.drop_index("ix_review_jobs_status", table_name="review_jobs")
    op.drop_index("ix_review_jobs_pull_request", table_name="review_jobs")
    op.drop_index("ix_review_jobs_repository", table_name="review_jobs")
    op.drop_table("review_jobs")
