"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── documents ──────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("page_count", sa.Integer),
        sa.Column("is_ocr", sa.Boolean, default=False),
        sa.Column("raw_text", sa.Text),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", "warning", name="processingstatus"),
            default="pending",
        ),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── invoices ───────────────────────────────────────────────────────────────
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), unique=True, nullable=False),
        sa.Column("vendor_name", sa.String(255)),
        sa.Column("vendor_address", sa.Text),
        sa.Column("invoice_number", sa.String(100)),
        sa.Column("invoice_date", sa.Date),
        sa.Column("due_date", sa.Date),
        sa.Column("payment_terms", sa.String(100)),
        sa.Column("notes", sa.Text),
        sa.Column("currency", sa.String(10)),
        sa.Column("subtotal", sa.Numeric(14, 2)),
        sa.Column("tax", sa.Numeric(14, 2)),
        sa.Column("total", sa.Numeric(14, 2)),
        sa.Column("total_usd", sa.Numeric(14, 2)),
        sa.Column(
            "category",
            sa.Enum(
                "Office Supplies", "Software/SaaS", "Travel", "Consulting",
                "Marketing", "Utilities", "Equipment", "Other",
                name="expensecategory",
            ),
        ),
        sa.Column("category_confidence", sa.Numeric(4, 3)),
        sa.Column("summary", sa.Text),
        sa.Column("days_until_due", sa.Integer),
        sa.Column("is_overdue", sa.Boolean),
        sa.Column("is_duplicate", sa.Boolean, default=False),
        sa.Column("anomaly_flags", postgresql.JSON),
        sa.Column("validation_status", sa.String(20), default="pending"),
        sa.Column("validation_errors", postgresql.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── line_items ─────────────────────────────────────────────────────────────
    op.create_table(
        "line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("quantity", sa.Numeric(10, 4)),
        sa.Column("unit_price", sa.Numeric(14, 2)),
        sa.Column("total", sa.Numeric(14, 2)),
    )

    # ── processing_logs ────────────────────────────────────────────────────────
    op.create_table(
        "processing_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("task_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("error", sa.Text),
        sa.Column("metadata", postgresql.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("processing_logs")
    op.drop_table("line_items")
    op.drop_table("invoices")
    op.drop_table("documents")
    op.execute("DROP TYPE IF EXISTS processingstatus")
    op.execute("DROP TYPE IF EXISTS expensecategory")
